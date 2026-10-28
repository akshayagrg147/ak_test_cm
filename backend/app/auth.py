import secrets
import time
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .common import dump
from .config import settings
from .db import get_db, now
from .models import AuthSession, LoginGuard, User
from .schemas import LoginIn, PasswordIn, Payload
from .security import (
    check_current,
    current,
    decode,
    decrypt,
    digest,
    encrypt,
    fail,
    new_session,
    passwords,
    phone,
    require_browser_request,
    token,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
DUMMY_HASH = passwords.hash("dummy-password-never-an-account")


def set_cookie(response, value):
    response.set_cookie(
        "crm_refresh",
        value,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        max_age=settings.refresh_days * 86400,
        path="/api/auth",
    )


def session_result(db, session):
    ctx = check_current(db, session)
    result = {
        "access_token": token(session.user_id, session.id),
        "user": dump(ctx.user),
        "role": ctx.role,
        "organization": dump(ctx.org),
        "support": bool(session.support_org),
        "support_until": session.support_until,
    }
    if session.acting_user_id:
        administrator = db.get(User, session.user_id)
        result["acting_as"] = {
            "administrator": {"id": administrator.id, "name": administrator.name},
            "until": session.acting_until,
        }
    return result


@router.post("/login")
def login(data: LoginIn, response: Response, request: Request, db: Session = Depends(get_db, scope="function")):
    normalized = phone(data.phone)
    key = digest(normalized + (request.client.host if request.client else "unknown"))
    # INSERT ON CONFLICT ensures attempts remain bounded across concurrent workers.
    from sqlalchemy.dialects.postgresql import insert

    db.execute(insert(LoginGuard).values(key=key, attempts=0, window=now()).on_conflict_do_nothing())
    guard = db.scalar(select(LoginGuard).where(LoginGuard.key == key).with_for_update())
    if guard.window < now() - timedelta(minutes=15):
        guard.attempts, guard.window = 0, now()
    if guard.attempts >= 10:
        fail("login_rate_limited", "Too many attempts. Try again in 15 minutes", 429)
    guard.attempts += 1
    db.commit()
    user = db.scalar(select(User).where(User.phone == normalized).with_for_update())
    try:
        valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    except Exception:
        valid = False
    if not user or not valid or not user.active:
        fail("invalid_credentials", "Phone or password is incorrect", 401)
    if user.totp_enabled:
        if not data.challenge or not data.code:
            return {"challenge_required": True, "challenge": token(user.id, secrets.token_hex(16), "challenge", 5)}
        claims = decode(data.challenge, "challenge")
        if claims["sub"] != user.id:
            fail("invalid_challenge", "Invalid two-factor challenge", 401)
        totp = pyotp.TOTP(decrypt(user.totp_secret))
        step = int(time.time()) // 30
        if step <= user.totp_last_step or not totp.verify(data.code):
            fail("invalid_code", "The authenticator code is invalid or already used", 401)
        user.totp_last_step = step
    session, refresh = new_session(db, user)
    result = session_result(db, session)
    guard.attempts = 0
    set_cookie(response, refresh)
    return result


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    require_browser_request(request)
    old = request.cookies.get("crm_refresh", "")
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_hash == digest(old)).with_for_update())
    try:
        check_current(db, session)
    except HTTPException as exc:
        if session and session.acting_user_id and exc.detail.get("code") in {"member_login_expired", "member_unavailable", "support_expired"}:
            from .member_login import restore_administrator

            return restore_administrator(db, session, response)
        raise
    replacement = secrets.token_urlsafe(48)
    session.refresh_hash = digest(replacement)
    set_cookie(response, replacement)
    return session_result(db, session)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    require_browser_request(request)
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_hash == digest(request.cookies.get("crm_refresh", "")))
        .with_for_update()
    )
    if session:
        session.revoked = True
        if session.acting_user_id:
            parent = db.get(AuthSession, session.parent_session_id)
            if parent and parent.user_id == session.user_id:
                parent.revoked = True
    response.delete_cookie("crm_refresh", path="/api/auth")
    return {"ok": True}


@router.get("/me")
def me(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    return session_result(db, ctx.session)


@router.post("/password")
def password(data: PasswordIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    user = db.scalar(select(User).where(User.id == ctx.id).with_for_update())
    if not passwords.verify(data.current, user.password_hash):
        fail("invalid_password", "Current password is incorrect", 401)
    user.password_hash = passwords.hash(data.password)
    db.execute(
        update(AuthSession).where(
            (AuthSession.user_id == user.id) | (AuthSession.acting_user_id == user.id),
            AuthSession.id != ctx.session.id,
        ).values(revoked=True)
    )
    return {"ok": True}


class TotpIn(Payload):
    password: str
    code: str = ""


@router.post("/2fa/setup")
def setup(data: TotpIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    user = db.scalar(select(User).where(User.id == ctx.id).with_for_update())
    if not passwords.verify(data.password, user.password_hash):
        fail("invalid_password", "Current password is incorrect", 401)
    if user.totp_enabled:
        fail("already_enabled", "Disable the current authenticator before replacing it", 409)
    secret = pyotp.random_base32()
    user.totp_secret = encrypt(secret)
    return {"secret": secret, "uri": pyotp.TOTP(secret).provisioning_uri(user.phone, issuer_name=settings.brand_name)}


@router.post("/2fa/{action}")
def toggle_totp(action: str, data: TotpIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    user = db.scalar(select(User).where(User.id == ctx.id).with_for_update())
    if action not in ["enable", "disable"]:
        fail("not_found", "Unknown action", 404)
    if (
        not passwords.verify(data.password, user.password_hash)
        or not user.totp_secret
        or not pyotp.TOTP(decrypt(user.totp_secret)).verify(data.code)
    ):
        fail("invalid_code", "Password or authenticator code is incorrect", 401)
    user.totp_enabled = action == "enable"
    user.totp_last_step = int(time.time()) // 30
    if action == "disable":
        user.totp_secret = None
    db.execute(
        update(AuthSession).where(
            (AuthSession.user_id == user.id) | (AuthSession.acting_user_id == user.id),
            AuthSession.id != ctx.session.id,
        ).values(revoked=True)
    )
    return {"ok": True}
