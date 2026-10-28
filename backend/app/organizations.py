from fastapi import APIRouter, Depends, File, Query, Response, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .auth import session_result, set_cookie
from .common import audit, dump, get_scoped, init_org, member, mutate, rows
from .db import get_db, now
from .models import AuthSession, Lead, Organization, User
from .schemas import CompanyAdminPatch, CompanyProfile, MemberIn, MemberPatch, OrganizationIn, OrganizationPatch
from .security import (
    Context,
    current,
    digest,
    fail,
    lock_org,
    new_session,
    passwords,
    phone,
    require_browser_request,
    roles,
    workspace,
)

router = APIRouter(prefix="/api", tags=["Organizations & team"])


@router.get("/platform")
def platform(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    orgs = list(
        db.scalars(select(Organization).where(Organization.deleted.is_(False)).order_by(Organization.created_at.desc()))
    )
    result = []
    for org in orgs:
        item = dump(org)
        from .billing import subscription_dump

        item["subscription"] = subscription_dump(db, org.id)
        item["users"] = db.scalar(
            select(func.count()).select_from(User).where(User.org_id == org.id, User.deleted.is_(False))
        )
        item["leads"] = db.scalar(
            select(func.count()).select_from(Lead).where(Lead.org_id == org.id, Lead.deleted.is_(False))
        )
        result.append(item)
    return {
        "organizations": result,
        "total": len(orgs),
        "active": sum(o.active for o in orgs),
        "users": sum(o["users"] for o in result),
        "leads": sum(o["leads"] for o in result),
    }


@router.post("/platform/organizations", status_code=201)
def create_org(data: OrganizationIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    if data.admin.role != "admin":
        fail("admin_required", "The first member must be an administrator", 422)
    normalized = phone(data.admin.phone)
    if db.scalar(select(User).where(User.phone == normalized)):
        fail("duplicate_phone", "This login phone is already in use", 409)
    org = Organization(name=data.name, settings={"industry": data.industry, "brand_name": data.brand_name,
                                               "company_profile": data.profile.model_dump()})
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        name=data.admin.name,
        phone=normalized,
        password_hash=passwords.hash(data.admin.password),
        role="admin",
    )
    db.add(user)
    init_org(db, org)
    if data.industry == "real_estate":
        from datetime import timedelta
        from .billing import today
        from .models import CompanySubscription

        db.add(CompanySubscription(org_id=org.id, starts_on=today(), ends_on=today() + timedelta(days=data.trial_days - 1), seats=5))
    db.flush()
    return {"organization": dump(org), "admin": dump(user)}


@router.get("/platform/organizations/{org_id}")
def org_detail(org_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    org = db.get(Organization, org_id)
    if not org or org.deleted:
        fail("not_found", "Organization not found", 404)
    from .billing import subscription_dump

    return {
        "organization": dump(org),
        "subscription": subscription_dump(db, org.id),
        "members": [dump(u) for u in db.scalars(rows(db, User, org_id).where(User.deleted.is_(False)))],
    }


@router.patch("/platform/organizations/{org_id}")
def patch_org(
    org_id: str, data: OrganizationPatch, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "owner")
    org = lock_org(db, org_id)
    if not org or org.deleted:
        fail("not_found", "Organization not found", 404)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None:
            fail("invalid_value", "Fields cannot be null", 422)
        if key in {"profile", "brand_name"}:
            org.settings = {**org.settings, "company_profile" if key == "profile" else key: value}
        else:
            setattr(org, key, value)
    if not org.active:
        ids = select(User.id).where(User.org_id == org_id)
        db.execute(
            update(AuthSession)
            .where((AuthSession.user_id.in_(ids)) | (AuthSession.support_org == org_id))
            .values(revoked=True)
        )
    from .models import Audit

    db.add(
        Audit(
            org_id=org_id,
            actor_id=ctx.id,
            entity="organization",
            entity_id=org_id,
            action="updated",
            summary="Organization details or active state changed",
        )
    )
    return dump(org)


@router.delete("/platform/organizations/{org_id}")
def delete_org(
    org_id: str, confirmation: str = Query(), ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "owner")
    org = lock_org(db, org_id)
    if not org or org.deleted:
        fail("not_found", "Organization not found", 404)
    if confirmation != org.name:
        fail("confirmation_required", "Type the exact organization name to delete", 422)
    from .models import SubscriptionPayment

    if db.scalar(rows(db, SubscriptionPayment, org_id).where(SubscriptionPayment.status == "pending")):
        fail("payment_pending", "Review pending subscription payments before archiving this company", 409)
    org.active, org.deleted = False, True
    db.execute(
        update(AuthSession)
        .where(
            (AuthSession.user_id.in_(select(User.id).where(User.org_id == org_id)))
            | (AuthSession.support_org == org_id)
        )
        .values(revoked=True)
    )
    from .models import Audit

    db.add(
        Audit(
            org_id=org_id,
            actor_id=ctx.id,
            entity="organization",
            entity_id=org_id,
            action="deleted",
            summary="Organization archived; records retained for recovery",
        )
    )
    return {
        "ok": True,
        "retention": "Archived with access revoked. Data retained for recovery; purge is an operator action.",
    }


@router.post("/platform/organizations/{org_id}/support")
def support(org_id: str, response: Response, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    org = lock_org(db, org_id)
    if not org or not org.active or org.deleted:
        fail("organization_unavailable", "This organization is unavailable", 409)
    session, refresh = new_session(db, ctx.user, org_id)
    set_cookie(response, refresh)
    from .models import Audit

    db.add(
        Audit(
            org_id=org_id,
            actor_id=ctx.id,
            entity="organization",
            entity_id=org_id,
            action="support_started",
            summary="Platform owner entered 30-minute support session",
        )
    )
    return session_result(db, session)


@router.post("/auth/support/exit")
def exit_support(request: Request, response: Response, db: Session = Depends(get_db, scope="function")):
    require_browser_request(request)
    support_session = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_hash == digest(request.cookies.get("crm_refresh", "")))
        .with_for_update()
    )
    if not support_session or support_session.revoked or support_session.expires_at <= now():
        fail("session_expired", "Sign in again to return to the platform", 401)
    user = db.get(User, support_session.user_id)
    if not user or not user.active or user.role != "owner" or not support_session.support_org or support_session.acting_user_id:
        fail("permission_denied", "No support session is active", 403)
    ctx = Context(user, support_session, db.get(Organization, support_session.support_org), "admin")
    audit(db, ctx, "organization", ctx.org_id, "support_ended", "Platform owner exited support session")
    ctx.session.revoked = True
    session, refresh = new_session(db, ctx.user)
    set_cookie(response, refresh)
    return session_result(db, session)


@router.get("/directory")
def directory(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    query = rows(db, User, ctx.org_id).where(User.active.is_(True), User.deleted.is_(False))
    if ctx.role == "telecaller":
        query = query.where(User.role.in_(["manager", "field_executive"]) | (User.id == ctx.id))
    elif ctx.role == "field_executive":
        query = query.where(User.role.in_(["manager", "admin"]) | (User.id == ctx.id))
    return [{"id": u.id, "name": u.name, "role": u.role} for u in db.scalars(query.order_by(User.name))]


@router.get("/team")
def team(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin", "manager")
    return [dump(u) for u in db.scalars(rows(db, User, ctx.org_id).where(User.deleted.is_(False)).order_by(User.name))]


@router.post("/team", status_code=201)
def add_member(data: MemberIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    from .billing import seat_limit

    seat_limit(db, ctx.org_id)
    normalized = phone(data.phone)
    if db.scalar(select(User).where(User.phone == normalized)):
        fail("duplicate_phone", "This login phone is already in use", 409)
    user = User(
        org_id=ctx.org_id, name=data.name, phone=normalized, password_hash=passwords.hash(data.password), role=data.role
    )
    db.add(user)
    db.flush()
    audit(db, ctx, "user", user.id, "created", f"Added {user.name} as {user.role}")
    return dump(user)


def guard_last_admin(db, ctx, user):
    if user.role == "admin" and user.active:
        count = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.org_id == user.org_id, User.role == "admin", User.active.is_(True), User.deleted.is_(False))
        )
        if count <= 1:
            fail("last_admin", "Keep at least one active administrator", 409)


@router.post("/platform/organizations/{org_id}/admins", status_code=201)
def add_company_admin(
    org_id: str, data: MemberIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    from .billing import company, owner_check, seat_limit
    from .models import Audit

    roles(ctx, "owner")
    org = company(db, org_id)
    owner_check(db, ctx)
    if data.role != "admin":
        fail("admin_required", "Use this action to create a company administrator", 422)
    seat_limit(db, org.id)
    normalized = phone(data.phone)
    if db.scalar(select(User).where(User.phone == normalized)):
        fail("duplicate_phone", "This login phone is already in use", 409)
    user = User(org_id=org.id, name=data.name, phone=normalized, password_hash=passwords.hash(data.password), role="admin")
    db.add(user)
    db.flush()
    db.add(Audit(org_id=org.id, actor_id=ctx.id, entity="user", entity_id=user.id,
                 action="admin_created", summary=f"Super admin created company administrator {user.name}"))
    return dump(user)


@router.patch("/platform/organizations/{org_id}/admins/{user_id}")
def edit_company_admin(
    org_id: str, user_id: str, data: CompanyAdminPatch,
    ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    from .billing import company, owner_check, seat_limit
    from .models import Audit

    roles(ctx, "owner")
    org = company(db, org_id)
    owner_check(db, ctx)
    user = db.scalar(rows(db, User, org.id).where(User.id == user_id, User.role == "admin", User.deleted.is_(False)))
    if not user:
        fail("not_found", "Company administrator not found", 404)
    values = data.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        fail("invalid_value", "Fields cannot be null", 422)
    if values.get("active") is False:
        guard_last_admin(db, ctx, user)
    if values.get("active") is True and not user.active:
        seat_limit(db, org.id)
    if "phone" in values:
        values["phone"] = phone(values["phone"])
        if db.scalar(select(User).where(User.phone == values["phone"], User.id != user.id)):
            fail("duplicate_phone", "This login phone is already in use", 409)
    revoke_sessions = "password" in values or any(
        key in values and values[key] != getattr(user, key) for key in ["phone", "active"]
    )
    for key, value in values.items():
        if key == "password":
            user.password_hash = passwords.hash(value)
        else:
            setattr(user, key, value)
    if revoke_sessions:
        db.execute(update(AuthSession).where(
            (AuthSession.user_id == user.id) | (AuthSession.acting_user_id == user.id)
        ).values(revoked=True))
    db.add(Audit(org_id=org.id, actor_id=ctx.id, entity="user", entity_id=user.id,
                 action="admin_updated", summary=f"Super admin updated company administrator {user.name}",
                 details={"fields": sorted(values)}))
    return dump(user)


@router.patch("/team/{user_id}")
def patch_member(
    user_id: str, data: MemberPatch, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    user = get_scoped(db, User, user_id, ctx)
    if user.deleted:
        fail("not_found", "Member not found", 404)
    values = data.model_dump(exclude_unset=True)
    if any(v is None for v in values.values()):
        fail("invalid_value", "Fields cannot be null", 422)
    if values.get("active") is False or ("role" in values and values["role"] != user.role):
        from .field_work import guard_field_member
        guard_field_member(db, ctx.org_id, user.id)
    if ctx.role == "manager" and (user.role not in {"telecaller", "field_executive"} or set(values) - {"active"}):
        fail("permission_denied", "Managers can only change a telecaller or field executive's active state", 403)
    if values.get("active") is True and not user.active:
        from .billing import seat_limit

        seat_limit(db, ctx.org_id)
    if values.get("active") is False or ("role" in values and values["role"] != "admin"):
        guard_last_admin(db, ctx, user)
    for key, value in values.items():
        if key == "password":
            user.password_hash = passwords.hash(value)
        else:
            setattr(user, key, value)
    if set(values) & {"password", "role", "active"}:
        db.execute(update(AuthSession).where(
            (AuthSession.user_id == user.id) | (AuthSession.acting_user_id == user.id)
        ).values(revoked=True))
    audit(db, ctx, "user", user.id, "updated", f"Updated member {user.name}", {"fields": list(values)})
    return dump(user)


@router.put("/company-profile")
def company_profile(data: CompanyProfile, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    ctx.org.settings = {**ctx.org.settings, "company_profile": data.model_dump()}
    audit(db, ctx, "organization", ctx.org_id, "profile_updated", "Company profile updated")
    return dump(ctx.org)


@router.post("/platform/organizations/{org_id}/logo", status_code=201)
async def company_logo(org_id: str, file: UploadFile = File(), ctx=Depends(current),
                       db: Session = Depends(get_db, scope="function")):
    from hashlib import sha256
    from pathlib import Path
    from .billing import company, owner_check, platform_audit
    from .files import content_type, store, validate_content
    from .imports import bounded_upload
    from .models import Attachment

    roles(ctx, "owner")
    org = company(db, org_id)
    owner_check(db, ctx)
    raw = await bounded_upload(file, 5 * 1024 * 1024)
    mime = content_type(raw)
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        fail("image_required", "Upload a PNG, JPEG or WebP logo", 422)
    validate_content(raw, mime)
    item = Attachment(org_id=org.id, author_id=ctx.id, name=Path((file.filename or "logo").replace("\\", "/")).name[:200],
                      mime=mime, storage_key=store(raw), digest=sha256(raw).hexdigest(), size=len(raw))
    db.add(item)
    db.flush()
    org.settings = {**org.settings, "logo_id": item.id}
    platform_audit(db, ctx, org.id, "logo_updated", "Super admin uploaded company logo")
    return dump(org)


@router.get("/platform/organizations/{org_id}/logo")
def read_company_logo(org_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    from .config import settings
    from .models import Attachment

    roles(ctx, "owner")
    org = db.get(Organization, org_id)
    logo_id = org.settings.get("logo_id") if org and not org.deleted else None
    logo = db.get(Attachment, logo_id) if logo_id else None
    if not logo or logo.org_id != org_id or not (settings.storage_path / logo.storage_key).is_file():
        fail("not_found", "Company logo not found", 404)
    return FileResponse(settings.storage_path / logo.storage_key, media_type=logo.mime,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/platform/organizations/{org_id}/logo")
def remove_company_logo(org_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    from .billing import company, owner_check, platform_audit

    roles(ctx, "owner")
    org = company(db, org_id)
    owner_check(db, ctx)
    org.settings = {key: value for key, value in org.settings.items() if key != "logo_id"}
    platform_audit(db, ctx, org.id, "logo_removed", "Super admin removed company logo")
    return dump(org)


@router.delete("/team/{user_id}")
def remove_member(
    user_id: str,
    confirmation: str = Query(),
    manager_id: str | None = None,
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    roles(ctx, "admin")
    mutate(db, ctx)
    user = get_scoped(db, User, user_id, ctx)
    if confirmation != user.name:
        fail("confirmation_required", "Type the member's exact name", 422)
    from .field_work import guard_field_member
    guard_field_member(db, ctx.org_id, user.id)
    guard_last_admin(db, ctx, user)
    assigned = list(db.scalars(rows(db, Lead, ctx.org_id).where(Lead.owner_id == user.id, Lead.deleted.is_(False))))
    if assigned:
        if not manager_id or manager_id == user.id:
            fail("handoff_required", "Choose another active manager for this member's leads", 422)
        member(db, ctx, manager_id, "manager")
        from .common import assign

        for lead in assigned:
            assign(db, ctx, lead, manager_id, "member_removed")
    user.active, user.deleted = False, True
    db.execute(update(AuthSession).where(
        (AuthSession.user_id == user.id) | (AuthSession.acting_user_id == user.id)
    ).values(revoked=True))
    audit(db, ctx, "user", user.id, "removed", f"Removed {user.name}; handed off {len(assigned)} leads")
    return {"ok": True, "handed_off": len(assigned)}
