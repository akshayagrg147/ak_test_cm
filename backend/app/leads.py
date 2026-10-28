from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from .common import (
    assign,
    audit,
    csv_response,
    dump,
    event,
    get_scoped,
    lead_access,
    lead_dump,
    lead_condition,
    member,
    mutate,
    rows,
    validate_lead,
)
from .db import get_db, now
from .models import (
    Assignment,
    Definition,
    Attachment,
    Audit,
    AutomationRun,
    Job,
    Lead,
    ManualCall,
    Note,
    PhoneCall,
    Provenance,
    Task,
    User,
)
from .schemas import AssignIn, LeadIn, LeadPatch, NoteIn, OutcomeIn, Source, Status, unique_interests
from .security import current, fail, phone, roles, workspace

router = APIRouter(prefix="/api/leads", tags=["Leads"])


def lead_query(
    ctx,
    q="",
    status=None,
    source=None,
    owner_id=None,
    category=None,
    interest=None,
    city=None,
    state=None,
    dnd=None,
    callback=None,
    from_date=None,
    to_date=None,
    stage=None,
    reported_by=None,
    reason=None,
):
    workspace(ctx)
    query = select(Lead).where(Lead.org_id == ctx.org_id, Lead.deleted.is_(False))
    query = query.where(lead_condition(ctx))
    if q:
        query = query.where(
            or_(*(column.icontains(q[:160], autoescape=True) for column in [Lead.name, Lead.phone, Lead.city]))
        )
    for column, value in [
        (Lead.status, status),
        (Lead.source, source),
        (Lead.stage, stage),
        (Lead.reported_by, reported_by),
    ]:
        if value:
            query = query.where(column == value)
    for column, value in [(Lead.city, city), (Lead.state, state)]:
        if value and value.strip():
            query = query.where(func.lower(func.trim(column)) == value.strip().lower())
    if owner_id:
        query = query.where(Lead.owner_id.is_(None) if owner_id == "unassigned" else Lead.owner_id == owner_id)
    if category:
        # JSON containment on the portable JSON column via PostgreSQL jsonb cast.
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB

        query = query.where(or_(Lead.category == category, cast(Lead.interests, JSONB).contains([category])))
    if interest:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB

        values = (
            func.jsonb_array_elements_text(cast(Lead.interests, JSONB))
            .table_valued("value")
            .render_derived(name="interest_values")
        )
        query = query.where(
            select(1)
            .select_from(values)
            .where(values.c.value.icontains(interest[:160], autoescape=True))
            .correlate(Lead)
            .exists()
        )
    if dnd is not None:
        query = query.where(Lead.dnd == dnd)
    if callback == "overdue":
        query = query.where(Lead.follow_up < now())
    elif callback == "upcoming":
        query = query.where(Lead.follow_up >= now())
    elif callback == "stale":
        query = query.where(Lead.last_contact.is_(None), Lead.created_at < now() - timedelta(hours=48))
    if from_date:
        query = query.where(Lead.created_at >= from_date)
    if to_date:
        query = query.where(Lead.created_at < to_date)
    if reason:
        query = query.where(Lead.lost_reason.icontains(reason[:160], autoescape=True))
    return query


def filters(
    q: str = "",
    status: Status | None = None,
    source: Source | None = None,
    owner_id: str | None = None,
    category: str | None = None,
    interest: str | None = None,
    city: str | None = None,
    state: str | None = None,
    dnd: bool | None = None,
    callback: Literal["overdue", "upcoming", "stale"] | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    stage: str | None = None,
    reported_by: str | None = None,
    reason: str | None = None,
):
    if any(v and v.tzinfo is None for v in [from_date, to_date]):
        fail("timezone_required", "Include timezones in date filters", 422)
    if from_date and to_date and from_date >= to_date:
        fail("invalid_date_range", "The end must be after the start", 422)
    return locals()


@router.get("")
def list_leads(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    f: dict = Depends(filters),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    query = lead_query(ctx, **f)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    if ctx.role == "telecaller":
        priority = case((Lead.follow_up < now(), 0), (Lead.last_contact.is_(None), 1), else_=2)
        query = query.order_by(priority, Lead.follow_up.asc().nulls_last(), Lead.created_at.asc(), Lead.id)
    else:
        query = query.order_by(case((Lead.owner_id.is_(None), 0), else_=1), Lead.created_at.desc(), Lead.id)
    return {
        "items": [lead_dump(db, obj) for obj in db.scalars(query.offset((page - 1) * size).limit(size))],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/export")
def export_leads(f: dict = Depends(filters), ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    items = list(db.scalars(lead_query(ctx, **f).order_by(Lead.created_at).limit(50001)))
    if len(items) > 50000:
        fail("export_too_large", "Narrow the filters to at most 50,000 leads", 422)
    return csv_response(
        [{**lead_dump(db, obj), "interests": "|".join(obj.interests)} for obj in items],
        [
            "name",
            "phone",
            "city",
            "state",
            "source",
            "status",
            "stage",
            "owner_name",
            "dnd",
            "category",
            "interests",
            "created_at",
            "follow_up",
            "notes",
        ],
    )


def create_lead(db, ctx, data, provider=False):
    values = data.model_dump(exclude={"allow_duplicate"})
    values["phone"] = phone(values["phone"])
    validate_lead(db, ctx, values)
    duplicate = db.scalar(rows(db, Lead, ctx.org_id).where(Lead.phone == values["phone"], Lead.deleted.is_(False)))
    if duplicate and not data.allow_duplicate:
        # Do not leak another caller's lead identity.
        fail(
            "duplicate_lead",
            "A lead with this phone already exists in the organization. Ask a manager to review it",
            409,
        )
    if values["status"] != "follow-up":
        values["follow_up"] = None
    elif values["follow_up"] <= now():
        fail("invalid_followup", "Schedule the next follow-up in the future", 422)
    owner = ctx.id if ctx.role in {"telecaller", "field_executive"} and not provider else None
    lead = Lead(org_id=ctx.org_id, **values)
    db.add(lead)
    db.flush()
    if owner:
        assign(db, ctx, lead, owner, "self_created")
    audit(db, ctx, "lead", lead.id, "created", f"Created lead {lead.name}")
    event(db, ctx.org_id, "lead_created", lead.id, ctx.id)
    return lead


@router.post("", status_code=201)
def add_lead(data: LeadIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    return lead_dump(db, create_lead(db, ctx, data))


@router.post("/assign")
def assign_leads(data: AssignIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    target = member(db, ctx, data.owner_id)
    if target.role not in ["manager", "telecaller"]:
        fail("invalid_assignee", "Assign leads to an active manager or telecaller", 422)
    if ctx.role in {"telecaller", "field_executive"} and target.role != "manager":
        fail("permission_denied", "You may only hand your leads to an active manager", 403)
    leads = [lead_access(db, ctx, lid) for lid in set(data.lead_ids)]
    for lead in leads:
        assign(db, ctx, lead, target.id, "handoff" if ctx.role == "telecaller" else "manual")
    return {"assigned": len(leads)}


@router.post("/distribute")
def distribute(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    callers = list(
        db.scalars(
            rows(db, User, ctx.org_id)
            .where(User.active.is_(True), User.deleted.is_(False), User.role == "telecaller")
            .order_by(User.created_at, User.id)
        )
    )
    if not callers:
        return {"assigned": 0, "message": "No active telecallers. Leads remain unassigned", "distribution": {}}
    leads = list(
        db.scalars(
            rows(db, Lead, ctx.org_id)
            .where(Lead.owner_id.is_(None), Lead.deleted.is_(False))
            .order_by(Lead.created_at, Lead.id)
            .with_for_update()
        )
    )
    distribution = {u.id: 0 for u in callers}
    for lead in leads:
        target = callers[ctx.org.cursor % len(callers)]
        assign(db, ctx, lead, target.id, "round_robin")
        distribution[target.id] += 1
        ctx.org.cursor += 1
    return {"assigned": len(leads), "distribution": distribution}


@router.get("/{lead_id}")
def detail(lead_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    return lead_dump(db, lead_access(db, ctx, lead_id))


@router.patch("/{lead_id}")
def patch_lead(lead_id: str, data: LeadPatch, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    lead = lead_access(db, ctx, lead_id)
    values = data.model_dump(exclude_unset=True)
    if any(v is None for v in values.values()):
        fail("invalid_value", "Lead fields cannot be null", 422)
    if "phone" in values:
        values["phone"] = phone(values["phone"])
        duplicate = db.scalar(
            rows(db, Lead, ctx.org_id).where(Lead.phone == values["phone"], Lead.id != lead.id, Lead.deleted.is_(False))
        )
        if duplicate:
            fail("duplicate_lead", "This phone belongs to another lead; review or merge it", 409)
    validate_lead(db, ctx, {**dump(lead), **values})
    changes = {k: {"from": getattr(lead, k), "to": v} for k, v in values.items() if getattr(lead, k) != v}
    for key, value in values.items():
        setattr(lead, key, value)
    audit(db, ctx, "lead", lead.id, "updated", "Lead details updated", changes)
    return lead_dump(db, lead)


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: str, confirmation: str = Query(), ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    lead = lead_access(db, ctx, lead_id)
    if confirmation != lead.name:
        fail("confirmation_required", "Type the exact lead name", 422)
    from .field_work import ACTIVE
    from .models import FieldHandoff
    if db.scalar(rows(db, FieldHandoff, ctx.org_id).where(FieldHandoff.lead_id == lead.id, FieldHandoff.current.is_(True), FieldHandoff.status.in_(ACTIVE))):
        fail("field_work_in_use", "Close or cancel this client's active field work before archiving", 409)
    from .models import Booking, SiteVisit

    if db.scalar(rows(db, Booking, ctx.org_id).where(Booking.lead_id == lead.id, Booking.status.in_(["reserved", "booked"]))) or db.scalar(rows(db, SiteVisit, ctx.org_id).where(SiteVisit.lead_id == lead.id, SiteVisit.status == "scheduled")):
        fail("lead_in_use", "Resolve this customer's active bookings and scheduled site visits before archiving", 409)
    lead.deleted = True
    audit(db, ctx, "lead", lead.id, "deleted", "Lead archived with history retained")
    return {"ok": True}


@router.get("/{lead_id}/history")
def history(
    lead_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    lead_access(db, ctx, lead_id)
    result = {}
    totals = {}
    for key, cls in [
        ("notes", Note),
        ("manual_calls", ManualCall),
        ("phone_calls", PhoneCall),
        ("assignments", Assignment),
        ("files", Attachment),
        ("tasks", Task),
    ]:
        query = rows(db, cls, ctx.org_id).where(cls.lead_id == lead_id)
        if ctx.role == "field_executive" and cls == Task:
            query = query.where(Task.owner_id == ctx.id)
        if ctx.role == "telecaller":
            if cls == PhoneCall:
                query = query.where(PhoneCall.user_id == ctx.id)
            elif cls == Task:
                query = query.where(Task.owner_id == ctx.id)
            elif cls == Attachment:
                query = query.where(
                    (Attachment.phone_call_id.is_(None))
                    | Attachment.phone_call_id.in_(
                        select(PhoneCall.id).where(PhoneCall.user_id == ctx.id, PhoneCall.org_id == ctx.org_id)
                    )
                )
        totals[key] = db.scalar(select(func.count()).select_from(query.subquery()))
        result[key] = [
            dump(obj)
            for obj in db.scalars(query.order_by(cls.created_at.desc(), cls.id).offset((page - 1) * size).limit(size))
        ]
        if cls == PhoneCall:
            for call in result[key]:
                call["recordings"] = [
                    dump(obj)
                    for obj in db.scalars(
                        rows(db, Attachment, ctx.org_id).where(Attachment.phone_call_id == call["id"])
                    )
                ]
    activity = rows(db, Audit, ctx.org_id).where(Audit.entity == "lead", Audit.entity_id == lead_id)
    totals["activity"] = db.scalar(select(func.count()).select_from(activity.subquery()))
    result["activity"] = [
        dump(obj)
        for obj in db.scalars(
            rows(db, Audit, ctx.org_id)
            .where(Audit.entity == "lead", Audit.entity_id == lead_id)
            .order_by(Audit.created_at.desc(), Audit.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ]
    ids = {
        item.get("author_id") or item.get("user_id") or item.get("actor_id")
        for values in result.values()
        for item in values
    }
    result["people"] = {
        u.id: u.name
        for u in db.scalars(select(User).where(User.id.in_(ids), (User.org_id == ctx.org_id) | (User.role == "owner")))
    }
    result["pagination"] = {"page": page, "size": size, "totals": totals}
    return result


@router.post("/{lead_id}/notes", status_code=201)
def add_note(lead_id: str, data: NoteIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    lead_access(db, ctx, lead_id)
    note = Note(org_id=ctx.org_id, lead_id=lead_id, author_id=ctx.id, text=data.text)
    db.add(note)
    db.flush()
    audit(db, ctx, "lead", lead_id, "note_added", "Added a note")
    return dump(note)


@router.put("/{lead_id}/notes/{note_id}")
def edit_note(
    lead_id: str, note_id: str, data: NoteIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    mutate(db, ctx)
    lead_access(db, ctx, lead_id)
    note = get_scoped(db, Note, note_id, ctx)
    if note.lead_id != lead_id or (note.author_id != ctx.id and ctx.role != "admin"):
        fail("permission_denied", "Only the author or an administrator can edit this note", 403)
    note.text = data.text
    audit(db, ctx, "lead", lead_id, "note_edited", "Updated a note")
    return dump(note)


@router.delete("/{lead_id}/notes/{note_id}")
def delete_note(lead_id: str, note_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    lead_access(db, ctx, lead_id)
    note = get_scoped(db, Note, note_id, ctx)
    if note.lead_id != lead_id or (note.author_id != ctx.id and ctx.role != "admin"):
        fail("permission_denied", "Only the author or an administrator can remove this note", 403)
    db.execute(
        update(Attachment).where(Attachment.org_id == ctx.org_id, Attachment.note_id == note.id).values(note_id=None)
    )
    db.delete(note)
    audit(db, ctx, "lead", lead_id, "note_removed", "Removed a note; files retained")
    return {"ok": True}


@router.post("/{lead_id}/outcomes", status_code=201)
def outcome(lead_id: str, data: OutcomeIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    lead = lead_access(db, ctx, lead_id)
    existing = db.scalar(
        rows(db, ManualCall, ctx.org_id).where(ManualCall.user_id == ctx.id, ManualCall.request_id == data.request_id)
    )
    if existing:
        if existing.lead_id != lead_id:
            fail("idempotency_conflict", "This request identifier belongs to another lead", 409)
        return dump(existing)
    if lead.dnd:
        fail(
            "dnd_enabled",
            "This lead is marked do not disturb. Remove DND only with appropriate consent before a contact action",
            409,
        )
    if data.phone_call_id:
        device_call = get_scoped(db, PhoneCall, data.phone_call_id, ctx)
        if device_call.lead_id != lead.id or device_call.user_id != ctx.id:
            fail("invalid_call", "Choose your device call for this lead", 422)
        if db.scalar(select(ManualCall).where(ManualCall.phone_call_id == device_call.id)):
            fail("already_linked", "This device call already has a business outcome", 409)
    if data.outcome == "follow-up" and data.follow_up <= now():
        fail("invalid_followup", "Schedule the next follow-up in the future", 422)
    if data.outcome in {"converted", "lost"}:
        from .field_work import ACTIVE
        from .models import FieldHandoff
        if db.scalar(rows(db, FieldHandoff, ctx.org_id).where(
            FieldHandoff.lead_id == lead.id, FieldHandoff.current.is_(True), FieldHandoff.status.in_(ACTIVE)
        )):
            fail("field_work_in_use", "Resolve this client's active field work before closing the lead outcome", 409)
    if data.outcome == "lost":
        manager = member(db, ctx, data.manager_id, "manager")
        lead.lost_reason, lead.reported_by = data.notes, ctx.id
        assign(db, ctx, lead, manager.id, "lost_handoff")
    previous = lead.status
    lead.status, lead.last_contact = data.outcome, now()
    lead.follow_up = data.follow_up if data.outcome == "follow-up" else None
    if data.outcome in ["converted", "lost"]:
        lead.stage = "won" if data.outcome == "converted" else "lost"
    elif lead.stage in ["won", "lost"] or db.scalar(
        rows(db, Definition, ctx.org_id).where(Definition.kind == "stage", Definition.key == lead.stage)
    ).config.get("closed", False):
        lead.stage = "qualified"
    call = ManualCall(
        org_id=ctx.org_id,
        lead_id=lead.id,
        user_id=ctx.id,
        duration=data.duration,
        notes=data.notes,
        outcome=data.outcome,
        order_value=data.order_value,
        request_id=data.request_id,
        phone_call_id=data.phone_call_id,
    )
    db.add(call)
    db.flush()
    audit(
        db,
        ctx,
        "lead",
        lead.id,
        "outcome",
        f"Recorded {data.outcome}",
        {"from_status": previous, "to_status": data.outcome, "source": "manual", "call_id": call.id},
    )
    if previous != lead.status:
        event(db, ctx.org_id, "status_changed", lead.id, ctx.id)
    return dump(call)


@router.post("/{primary_id}/merge/{duplicate_id}")
def merge(primary_id: str, duplicate_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    if primary_id == duplicate_id:
        fail("invalid_merge", "Choose two different leads", 422)
    primary, duplicate = lead_access(db, ctx, primary_id), lead_access(db, ctx, duplicate_id)
    from .models import FieldHandoff
    if db.scalar(rows(db, FieldHandoff, ctx.org_id).where(FieldHandoff.lead_id.in_([primary_id, duplicate_id]))):
        fail("field_merge_review", "These leads have field-work history. Keep them separate for review", 409)
    combined_interests = unique_interests([*primary.interests, *duplicate.interests])
    if len(combined_interests) > 30:
        fail("too_many_interests", "The merged lead would exceed 30 interests. Edit the interests before merging", 422)
    from .models import Booking, BuyerRequirement, SiteVisit

    primary_brief = db.scalar(rows(db, BuyerRequirement, ctx.org_id).where(BuyerRequirement.lead_id == primary_id))
    duplicate_brief = db.scalar(rows(db, BuyerRequirement, ctx.org_id).where(BuyerRequirement.lead_id == duplicate_id))
    if primary_brief and duplicate_brief:
        db.add(Note(org_id=ctx.org_id, lead_id=primary_id, author_id=ctx.id,
                    text="Property brief retained from merged lead " + duplicate.name + ": " + str(dump(duplicate_brief))))
        db.delete(duplicate_brief)
    elif duplicate_brief:
        duplicate_brief.lead_id = primary_id
    # Explicitly reparent every dependent type. The archived source remains an audit identity.
    for cls in [Note, Attachment, ManualCall, PhoneCall, Task, Assignment, Provenance, AutomationRun, Booking, SiteVisit]:
        db.execute(update(cls).where(cls.org_id == ctx.org_id, cls.lead_id == duplicate_id).values(lead_id=primary_id))
    db.execute(
        update(Audit)
        .where(Audit.org_id == ctx.org_id, Audit.entity == "lead", Audit.entity_id == duplicate_id)
        .values(entity_id=primary_id)
    )
    # Pending event payloads also follow the surviving record.
    for job in db.scalars(rows(db, Job, ctx.org_id).where(Job.state == "pending")):
        if job.payload.get("lead_id") == duplicate_id:
            job.payload = {**job.payload, "lead_id": primary_id}
    primary.interests = combined_interests
    primary.details = {**duplicate.details, **primary.details}
    primary.custom = {**duplicate.custom, **primary.custom}
    if duplicate.notes:
        db.add(
            Note(
                org_id=ctx.org_id,
                lead_id=primary_id,
                author_id=ctx.id,
                text=f"Merged from {duplicate.name}:\n{duplicate.notes}",
            )
        )
    duplicate.deleted = True
    audit(
        db,
        ctx,
        "lead",
        primary.id,
        "merged",
        f"Merged {duplicate.name} into {primary.name}",
        {"merged_id": duplicate.id, "preserved_phone": duplicate.phone},
    )
    return lead_dump(db, primary)
