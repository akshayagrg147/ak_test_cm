"""Temporary member sessions retain the administrator's authenticated identity."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import session_result, set_cookie
from .common import audit, get_scoped, mutate
from .db import get_db, now
from .models import AuthSession, Organization, User
from .security import Context, check_current, current, digest, fail, new_session, require_browser_request, roles

router = APIRouter(prefix="/api", tags=["Audited member login"])


@router.post("/team/{user_id}/login-as")
def login_as_member(user_id: str, request: Request, response: Response,
                    ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    require_browser_request(request)
    roles(ctx, "admin")
    if ctx.session.acting_user_id:
        fail("nested_member_login", "Return to your account before choosing another member", 403)
    mutate(db, ctx)
    roles(ctx, "admin")
    user = get_scoped(db, User, user_id, ctx)
    if not user.active or user.deleted:
        fail("member_unavailable", "Choose an active team member", 409)
    if user.id == ctx.id or user.role not in {"telecaller", "manager", "field_executive"}:
        fail("invalid_member_login", "Choose a telecaller, field executive or manager in your company", 403)
    session, refresh = new_session(db, ctx.user, ctx.session.support_org)
    session.acting_user_id = user.id
    session.parent_session_id = ctx.session.id
    session.expires_at = min(session.expires_at, ctx.session.expires_at)
    session.acting_until = min(now() + timedelta(minutes=30), session.expires_at)
    if ctx.session.support_until:
        session.support_until = ctx.session.support_until
        session.acting_until = min(session.acting_until, ctx.session.support_until)
    audit(db, ctx, "user", user.id, "member_login_started", f"{ctx.user.name} logged in as {user.name}")
    set_cookie(response, refresh)
    return session_result(db, session)


def restore_administrator(db, session, response):
    if not session or session.revoked or session.expires_at <= now() or not session.acting_user_id:
        fail("session_expired", "Sign in again to return to your account", 401)
    parent = db.scalar(select(AuthSession).where(AuthSession.id == session.parent_session_id)
                       .with_for_update().execution_options(populate_existing=True))
    if not parent or parent.acting_user_id or parent.user_id != session.user_id or parent.support_org != session.support_org:
        fail("invalid_session", "Your administrator session is unavailable", 401)
    try:
        administrator = check_current(db, parent)
    except HTTPException as exc:
        actor = db.get(User, parent.user_id)
        if exc.detail.get("code") != "support_expired" or not actor or actor.role != "owner":
            raise
        # Expired company support can only return its owner to the platform.
        administrator = Context(actor, parent, db.get(Organization, parent.support_org), "admin")
        audit(db, administrator, "user", session.acting_user_id, "member_login_ended", "Super admin returned from expired member support")
        session.revoked = parent.revoked = True
        restored, refresh = new_session(db, actor)
        set_cookie(response, refresh)
        return session_result(db, restored)
    roles(administrator, "admin")
    audit(db, administrator, "user", session.acting_user_id, "member_login_ended", "Administrator returned from member login")
    session.revoked = True
    refresh = secrets.token_urlsafe(48)
    parent.refresh_hash = digest(refresh)
    set_cookie(response, refresh)
    return session_result(db, parent)


@router.post("/auth/login-as/exit")
def exit_member_login(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    require_browser_request(request)
    session = db.scalar(select(AuthSession).where(
        AuthSession.refresh_hash == digest(request.cookies.get("crm_refresh", ""))
    ).with_for_update())
    return restore_administrator(db, session, response)
