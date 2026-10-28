from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .common import dump, mutate, rows
from .config import settings
from .db import get_db, now
from .models import Attachment, Lead, PhoneCall, User
from .schemas import PhoneSyncIn
from .security import current, fail, phone, roles, workspace

router = APIRouter(prefix="/api/phone-calls", tags=["Device phone calls"])


@router.get("/contacts")
def device_contacts(
    after: str = "",
    limit: int = Query(200, ge=1, le=200),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    """Only the user's current assigned customers may enter a device's work-call allowlist."""
    roles(ctx, "manager", "telecaller")
    query = rows(db, Lead, ctx.org_id).where(Lead.owner_id == ctx.id, Lead.deleted.is_(False), Lead.id > after)
    contacts = list(db.scalars(query.order_by(Lead.id).limit(limit + 1)))
    return {
        "items": [{"id": lead.id, "name": lead.name, "phone": lead.phone, "dnd": lead.dnd} for lead in contacts[:limit]],
        "next_cursor": contacts[limit - 1].id if len(contacts) > limit else None,
        "user_id": ctx.id,
        "organization_id": ctx.org_id,
        "max_recording_bytes": settings.max_recording_upload,
    }


@router.post("/sync")
def sync(data: PhoneSyncIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "manager", "telecaller")
    mutate(db, ctx)
    leads = list(db.scalars(rows(db, Lead, ctx.org_id).where(Lead.owner_id == ctx.id, Lead.deleted.is_(False))))
    mapping = {}
    for lead in leads:
        mapping.setdefault(lead.phone, []).append(lead)
    result = {"created": 0, "updated": 0, "excluded": 0, "ambiguous": 0, "errors": [], "entries": []}
    for entry in data.calls:
        receipt = {"device_call_id": entry.device_call_id}
        result["entries"].append(receipt)
        try:
            normalized = phone(entry.phone)
        except Exception:
            receipt.update(status="error", code="invalid_phone")
            result["errors"].append({"id": entry.device_call_id, "code": "invalid_phone"})
            continue
        matches = mapping.get(normalized, [])
        if not matches:
            receipt.update(status="excluded")
            result["excluded"] += 1
            continue
        if len(matches) != 1:
            receipt.update(status="ambiguous")
            result["ambiguous"] += 1
            continue
        if entry.started_at < now() - timedelta(days=30) or entry.started_at > now() + timedelta(minutes=5):
            receipt.update(status="error", code="outside_sync_window")
            result["errors"].append({"id": entry.device_call_id, "code": "outside_sync_window"})
            continue
        existing = db.scalar(
            rows(db, PhoneCall, ctx.org_id).where(
                PhoneCall.user_id == ctx.id,
                PhoneCall.device_id == data.device_id,
                PhoneCall.device_call_id == entry.device_call_id,
            )
        )
        if existing:
            if existing.lead_id != matches[0].id:
                # A reused/shared number must not restore access to a historical call
                # whose original lead was reassigned or archived.
                receipt.update(status="excluded")
                result["excluded"] += 1
                continue
            if (
                existing.phone != normalized
                or abs((existing.started_at - entry.started_at).total_seconds()) > 1
                or existing.direction != entry.direction
            ):
                receipt.update(status="error", code="identity_conflict")
                result["errors"].append({"id": entry.device_call_id, "code": "identity_conflict"})
                continue
            existing.duration = max(existing.duration, entry.duration)
            if entry.result != "unknown":
                existing.result = entry.result
            result["updated"] += 1
            call = existing
            receipt["status"] = "updated"
        else:
            call = PhoneCall(
                org_id=ctx.org_id,
                user_id=ctx.id,
                lead_id=matches[0].id,
                device_id=data.device_id,
                **{**entry.model_dump(), "phone": normalized},
            )
            db.add(call)
            db.flush()
            result["created"] += 1
            receipt["status"] = "created"
        receipt.update(call_id=call.id, lead_id=call.lead_id, recording_state=call.recording_state)
        lead = matches[0]
        if (
            entry.result == "answered"
            and entry.duration > 0
            and (not lead.last_contact or entry.started_at > lead.last_contact)
        ):
            lead.last_contact = entry.started_at
    return result


@router.get("")
def phone_calls(
    q: str = "",
    user_id: str | None = None,
    lead_id: str | None = None,
    direction: str | None = None,
    result: str | None = None,
    recording_state: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    workspace(ctx)
    if any(value and value.tzinfo is None for value in [from_date, to_date]):
        fail("timezone_required", "Include timezones in date filters", 422)
    if from_date and to_date and from_date >= to_date:
        fail("invalid_date_range", "The end must be after the start", 422)
    query = rows(db, PhoneCall, ctx.org_id).join(Lead, Lead.id == PhoneCall.lead_id).where(Lead.deleted.is_(False))
    if ctx.role == "telecaller":
        query = query.where(PhoneCall.user_id == ctx.id, Lead.owner_id == ctx.id)
    elif ctx.role == "field_executive":
        from .common import visible_lead_ids
        query = query.where(PhoneCall.lead_id.in_(visible_lead_ids(ctx)))
    for column, value in [
        (PhoneCall.user_id, user_id),
        (PhoneCall.lead_id, lead_id),
        (PhoneCall.direction, direction),
        (PhoneCall.result, result),
        (PhoneCall.recording_state, recording_state),
    ]:
        if value:
            query = query.where(column == value)
    if q:
        query = query.where((PhoneCall.phone.ilike(f"%{q[:100]}%")) | (Lead.name.ilike(f"%{q[:100]}%")))
    if from_date:
        query = query.where(PhoneCall.started_at >= from_date)
    if to_date:
        query = query.where(PhoneCall.started_at < to_date)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = []
    for call in db.scalars(query.order_by(PhoneCall.started_at.desc(), PhoneCall.id).offset((page - 1) * 50).limit(50)):
        item = dump(call)
        item["lead_name"] = db.get(Lead, call.lead_id).name
        item["user_name"] = db.get(User, call.user_id).name
        item["recordings"] = [
            dump(r)
            for r in db.scalars(
                select(Attachment).where(Attachment.org_id == ctx.org_id, Attachment.phone_call_id == call.id)
            )
        ]
        items.append(item)
    return {"items": items, "total": total, "page": page}
