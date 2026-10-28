import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

import jwt
import phonenumbers
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, now
from .models import AuthSession, Organization, User

passwords = PasswordHash.recommended()
fernet = Fernet(
    settings.encryption_key.encode()
    if settings.encryption_key
    else base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
)


def fail(code, message, status=400):
    raise HTTPException(status, detail={"code": code, "message": message})


def phone(value):
    try:
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        parsed = phonenumbers.parse(text, None if text.startswith("+") else "IN")
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError()
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        fail(
            "invalid_phone",
            "Enter a valid country-aware phone number, including +country code for international numbers",
            422,
        )


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt(value):
    return fernet.encrypt(value.encode()).decode()


def decrypt(value):
    return fernet.decrypt(value.encode()).decode()


def token(user_id, sid, kind="access", minutes=None):
    return jwt.encode(
        {
            "sub": user_id,
            "sid": sid,
            "kind": kind,
            "exp": now() + timedelta(minutes=minutes or settings.access_minutes),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def decode(value, kind="access"):
    try:
        claims = jwt.decode(
            value, settings.secret_key, algorithms=["HS256"], options={"require": ["sub", "sid", "exp", "kind"]}
        )
        if claims["kind"] != kind:
            raise ValueError()
        return claims
    except Exception:
        fail("session_expired", "Your session has expired. Please sign in again", 401)


@dataclass
class Context:
    user: User
    session: AuthSession
    org: Organization | None
    role: str

    @property
    def org_id(self):
        return self.org.id if self.org else None

    @property
    def id(self):
        return self.user.id

    @property
    def actor_id(self):
        return self.session.user_id if self.session.acting_user_id else self.id


def check_current(db, session):
    if not session or session.revoked or session.expires_at <= now():
        fail("session_expired", "Your session has expired. Please sign in again", 401)
    user = db.get(User, session.user_id, populate_existing=True)
    if not user or not user.active or user.deleted:
        fail("account_inactive", "This account is inactive", 401)
    org_id = user.org_id
    role = user.role
    if session.support_org:
        if user.role != "owner" or not session.support_until or session.support_until <= now():
            fail("support_expired", "Support access expired. Exit support mode and sign in again", 401)
        org_id, role = session.support_org, "admin"
    org = db.get(Organization, org_id) if org_id else None
    if org_id and (not org or not org.active or org.deleted):
        fail("organization_suspended", "This organization is suspended", 403)
    if session.acting_user_id:
        parent = db.get(AuthSession, session.parent_session_id, populate_existing=True)
        if (
            not parent or parent.acting_user_id or parent.user_id != session.user_id
            or parent.support_org != session.support_org
        ):
            fail("invalid_session", "The administrator session is unavailable. Sign in again", 401)
        administrator = check_current(db, parent)
        if administrator.role != "admin" or not administrator.org_id:
            fail("permission_denied", "Administrator access is required", 403)
        if not session.acting_until or session.acting_until <= now():
            fail("member_login_expired", "Member login expired. Return to your administrator account", 401)
        member = db.get(User, session.acting_user_id, populate_existing=True)
        if (
            not member or not member.active or member.deleted or member.org_id != administrator.org_id
            or member.role not in {"manager", "telecaller", "field_executive"} or member.id == administrator.id
        ):
            fail("member_unavailable", "This member login is no longer available", 401)
        user, role, org = member, member.role, administrator.org
    return Context(user, session, org, role)


def current(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db, scope="function"),
):
    if not credentials:
        fail("authentication_required", "Sign in to continue", 401)
    claims = decode(credentials.credentials)
    session = db.get(AuthSession, claims["sid"])
    if session and session.user_id != claims["sub"]:
        fail("invalid_session", "Invalid session", 401)
    ctx = check_current(db, session)
    if session.acting_user_id and request.url.path.startswith(("/api/auth/password", "/api/auth/2fa")):
        fail("member_security_protected", "Member passwords and authenticator settings require their own sign-in", 403)
    return ctx


def roles(ctx, *allowed):
    if ctx.role not in allowed:
        fail("permission_denied", "You do not have permission for this action", 403)


def workspace(ctx):
    if not ctx.org:
        fail("support_required", "Use the audited support flow to access an organization", 403)


def lock_org(db, org_id):
    return db.scalar(
        select(Organization)
        .where(Organization.id == org_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def new_session(db, user, support_org=None):
    secret = secrets.token_urlsafe(48)
    session = AuthSession(
        user_id=user.id,
        refresh_hash=digest(secret),
        expires_at=now() + timedelta(days=settings.refresh_days),
        support_org=support_org,
        support_until=now() + timedelta(minutes=30) if support_org else None,
    )
    db.add(session)
    db.flush()
    return session, secret


def require_browser_request(request: Request):
    if request.headers.get("x-requested-with") != "TalkoCRM":
        fail("csrf_rejected", "A protected browser request is required", 403)
    origin = request.headers.get("origin")
    if origin and origin != settings.public_origin:
        fail("csrf_rejected", "Request origin is not permitted", 403)
