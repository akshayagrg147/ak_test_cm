"""A caller keeps coordination; the assigned executive owns the field next step."""

import hashlib
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .business_schemas import HandoffChange, HandoffIn, VisitIn
from .common import audit, dump, lead_access, member, mutate, rows
from .db import get_db, now
from .models import Definition, FieldHandoff, Lead, Note, Property, SiteVisit, Task, User
from .real_estate import visit_dump, visit_values
from .security import current, fail, roles, workspace

router = APIRouter(prefix="/api/field-work", tags=["Field executive handoffs"])
ACTIVE = {"pending", "accepted", "follow_up", "ready_for_booking"}


def handoff_query(ctx):
    workspace(ctx)
    query = (
        rows(None, FieldHandoff, ctx.org_id).join(Lead, Lead.id == FieldHandoff.lead_id).where(Lead.deleted.is_(False))
    )
    if ctx.role == "telecaller":
        query = query.where(Lead.owner_id == ctx.id)
    elif ctx.role == "field_executive":
        query = query.where(FieldHandoff.executive_id == ctx.id, FieldHandoff.current.is_(True))
    return query


def handoff_dump(db, item):
    lead = db.get(Lead, item.lead_id)
    return {
        **dump(item),
        "lead_name": lead.name,
        "lead_phone": lead.phone,
        "executive_name": db.get(User, item.executive_id).name,
        "coordinator_name": db.get(User, lead.owner_id).name if lead.owner_id else "Unassigned",
        "created_by_name": db.get(User, item.creator_id).name,
        "visit": visit_dump(db, db.get(SiteVisit, item.visit_id)),
        "property_address": db.get(Property, db.get(SiteVisit, item.visit_id).property_id).address,
    }


def field_record(db, ctx, item_id):
    item = db.scalar(handoff_query(ctx).where(FieldHandoff.id == item_id))
    if not item:
        fail("not_found", "This handoff is not available to you", 404)
    return item


def guard_field_member(db, org_id, user_id):
    if db.scalar(
        rows(db, FieldHandoff, org_id).where(
            FieldHandoff.executive_id == user_id, FieldHandoff.current.is_(True), FieldHandoff.status.in_(ACTIVE)
        )
    ):
        fail("field_work_in_use", "Reassign or close this executive's active field work first", 409)


def linked_handoff(db, org_id, *, visit_id=None, task_id=None):
    column, value = (FieldHandoff.visit_id, visit_id) if visit_id else (FieldHandoff.task_id, task_id)
    return db.scalar(rows(db, FieldHandoff, org_id).where(column == value)) if value else None


@router.get("")
def handoffs(
    lead_id: str = "",
    q: str = "",
    status: str = "",
    executive_id: str = "",
    due: str = "",
    page: int = Query(1, ge=1),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    query = handoff_query(ctx)
    if lead_id:
        lead_access(db, ctx, lead_id)
        query = query.where(FieldHandoff.lead_id == lead_id)
    if q.strip():
        query = query.where(
            Lead.name.icontains(q[:160], autoescape=True) | Lead.phone.icontains(q[:160], autoescape=True)
        )
    if executive_id:
        query = query.where(FieldHandoff.executive_id == executive_id)
    summary = dict(
        db.execute(
            select(FieldHandoff.status, func.count())
            .where(FieldHandoff.id.in_(query.with_only_columns(FieldHandoff.id)))
            .group_by(FieldHandoff.status)
        ).all()
    )
    if status == "active":
        query = query.where(FieldHandoff.current.is_(True), FieldHandoff.status.in_(ACTIVE))
    elif status:
        if status not in ACTIVE | {"closed", "cancelled"}:
            fail("invalid_status", "Choose a field-work status", 422)
        query = query.where(FieldHandoff.status == status)
    if due:
        if due != "overdue":
            fail("invalid_due_filter", "Choose overdue next steps", 422)
        query = query.join(SiteVisit, SiteVisit.id == FieldHandoff.visit_id).where(
            FieldHandoff.current.is_(True),
            FieldHandoff.status.in_(ACTIVE),
            ((FieldHandoff.follow_up_at < now()) | ((SiteVisit.status == "scheduled") & (SiteVisit.starts_at < now()))),
        )
    return {
        "items": [
            handoff_dump(db, item)
            for item in db.scalars(
                query.order_by(FieldHandoff.updated_at.desc(), FieldHandoff.id).offset((page - 1) * 25).limit(25)
            )
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
        "summary": summary,
    }


@router.post("", status_code=201)
def create_handoff(data: HandoffIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager", "telecaller")
    mutate(db, ctx)
    roles(ctx, "admin", "manager", "telecaller")
    lead = lead_access(db, ctx, data.lead_id)
    fingerprint = hashlib.sha256(data.model_dump_json(exclude={"request_id"}).encode()).hexdigest()
    existing = db.scalar(rows(db, FieldHandoff, ctx.org_id).where(FieldHandoff.request_id == data.request_id))
    if existing:
        if existing.creator_id != ctx.id or existing.request_digest != fingerprint:
            fail("idempotency_conflict", "This request was already used for a different handoff", 409)
        return handoff_dump(db, existing)
    if ctx.org.settings.get("industry") != "real_estate":
        fail("real_estate_required", "Enable the real estate workspace before assigning field work", 409)
    if not data.client_confirmed:
        fail("client_confirmation_required", "Confirm that the client agreed to this visit", 422)
    if lead.status in {"lost", "converted"} or lead.dnd:
        fail("lead_not_ready", "Review this lead's closed outcome or do-not-contact setting before scheduling", 409)
    executive = member(db, ctx, data.executive_id, "field_executive")
    previous = db.scalar(
        rows(db, FieldHandoff, ctx.org_id).where(FieldHandoff.lead_id == lead.id, FieldHandoff.current.is_(True))
    )
    if previous and previous.status in ACTIVE:
        fail("handoff_exists", "This client already has active field work. Open it to reschedule or reassign", 409)
    values = visit_values(
        db,
        ctx,
        VisitIn(
            lead_id=lead.id,
            property_id=data.property_id,
            assignee_id=executive.id,
            starts_at=data.starts_at,
            duration_minutes=data.duration_minutes,
            notes=data.brief,
        ),
        field_handoff=True,
    )
    if previous:
        previous.current = False
        db.flush()
    visit = SiteVisit(org_id=ctx.org_id, creator_id=ctx.id, **values)
    db.add(visit)
    db.flush()
    item = FieldHandoff(
        org_id=ctx.org_id,
        lead_id=lead.id,
        executive_id=executive.id,
        creator_id=ctx.id,
        visit_id=visit.id,
        brief=data.brief,
        meeting_point=data.meeting_point,
        request_id=data.request_id,
        request_digest=fingerprint,
    )
    db.add(item)
    stage = db.scalar(
        rows(db, Definition, ctx.org_id).where(
            Definition.kind == "stage", Definition.key == "site_visit", Definition.active.is_(True)
        )
    )
    if stage and lead.stage in {"new", "qualified"}:
        lead.stage = stage.key
    db.flush()
    audit(
        db,
        ctx,
        "lead",
        lead.id,
        "field_handoff_created",
        f"Assigned field visit to {executive.name}",
        {"handoff_id": item.id, "executive_id": executive.id, "visit_id": visit.id},
    )
    return handoff_dump(db, item)


def finish_task(db, item, state="completed"):
    if item.task_id:
        task = db.get(Task, item.task_id)
        if task and task.state == "open":
            task.state = state
            task.completed_at = now() if state == "completed" else None
    item.task_id = None


def next_step(db, ctx, item, data):
    if data.next_step not in {"follow_up", "ready_for_booking", "closed"}:
        fail("next_step_required", "Choose the next step for this client", 422)
    if data.next_step == "follow_up":
        if (
            not data.follow_up_at
            or data.follow_up_at < now()
            or data.follow_up_at > now() + timedelta(days=5 * 366)
            or len(data.next_action.strip()) < 3
        ):
            fail("follow_up_required", "Enter a clear next action and a future follow-up date within five years", 422)
    elif data.follow_up_at or data.next_action:
        fail("irrelevant_follow_up", "Only a follow-up next step accepts an action and due date", 422)
    finish_task(db, item)
    item.status, item.feedback = data.next_step, data.feedback
    item.follow_up_at = data.follow_up_at if data.next_step == "follow_up" else None
    item.next_action = data.next_action if data.next_step == "follow_up" else ""
    if item.status == "follow_up":
        task = Task(
            org_id=ctx.org_id,
            lead_id=item.lead_id,
            owner_id=item.executive_id,
            creator_id=ctx.id,
            title=data.next_action,
            description="Field follow-up. Update this through Field work.",
            kind="callback",
            due_at=data.follow_up_at,
            priority="high",
        )
        db.add(task)
        db.flush()
        item.task_id = task.id
    db.add(
        Note(
            org_id=ctx.org_id,
            lead_id=item.lead_id,
            author_id=ctx.id,
            text="Field work — "
            + item.status.replace("_", " ")
            + ": "
            + data.feedback
            + (
                "\nNext action: " + item.next_action + " · " + item.follow_up_at.isoformat()
                if item.follow_up_at
                else ""
            ),
        )
    )


@router.patch("/{handoff_id}")
def change_handoff(
    handoff_id: str, data: HandoffChange, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    mutate(db, ctx)
    item = field_record(db, ctx, handoff_id)
    if data.version != item.version:
        fail("handoff_changed", "This handoff changed. Refresh it before saving again", 409)
    if not item.current or item.status not in ACTIVE:
        fail("handoff_closed", "This handoff is closed. Schedule a new handoff if needed", 409)
    visit = db.get(SiteVisit, item.visit_id)
    lead = db.get(Lead, item.lead_id)
    if data.action in {"reschedule", "visit_outcome", "follow_up"} and (
        lead.dnd or lead.status in {"lost", "converted"}
    ):
        fail(
            "lead_not_ready",
            "Review this client's closed outcome or do-not-contact setting; cancel field work if needed",
            409,
        )
    coordinator = ctx.role in {"admin", "manager", "telecaller"}
    executive = ctx.role == "field_executive" and ctx.id == item.executive_id
    if data.action == "accept":
        if not executive or item.status != "pending":
            fail("accept_forbidden", "Only the assigned field executive can accept a pending handoff", 403)
        item.status, item.accepted_at = "accepted", now()
    else:
        if len(data.feedback.strip()) < 3:
            fail("feedback_required", "Add a short explanation or client feedback", 422)
        if data.action == "reassign":
            roles(ctx, "admin", "manager")
            target = member(db, ctx, data.executive_id or "", "field_executive")
            if target.id == item.executive_id:
                fail("same_executive", "Choose a different field executive", 422)
            if visit.status == "scheduled":
                visit_values(
                    db,
                    ctx,
                    VisitIn(
                        lead_id=item.lead_id,
                        property_id=visit.property_id,
                        assignee_id=target.id,
                        starts_at=max(visit.starts_at, now()),
                        duration_minutes=visit.duration_minutes,
                    ),
                    visit.id,
                    field_handoff=True,
                )
                visit.assignee_id = target.id
            item.executive_id, item.accepted_at = target.id, None
            item.status = "pending"
            if item.task_id:
                db.get(Task, item.task_id).owner_id = target.id
        elif data.action == "reschedule":
            if not (coordinator or executive) or not data.starts_at:
                fail("schedule_required", "Select a new visit date and time", 422)
            values = visit_values(
                db,
                ctx,
                VisitIn(
                    lead_id=item.lead_id,
                    property_id=data.property_id or visit.property_id,
                    assignee_id=item.executive_id,
                    starts_at=data.starts_at,
                    duration_minutes=data.duration_minutes or visit.duration_minutes,
                    notes=item.brief,
                ),
                visit.id,
                field_handoff=True,
            )
            if visit.status == "scheduled":
                for key, value in values.items():
                    setattr(visit, key, value)
            else:
                visit = SiteVisit(org_id=ctx.org_id, creator_id=ctx.id, **values)
                db.add(visit)
                db.flush()
                item.visit_id = visit.id
            if data.meeting_point:
                item.meeting_point = data.meeting_point
            finish_task(db, item, "cancelled")
            item.follow_up_at, item.next_action = None, ""
            item.status = "accepted" if item.accepted_at else "pending"
        elif data.action in {"visit_outcome", "follow_up", "close"}:
            if ctx.role not in {"admin", "manager"} and not executive:
                fail("permission_denied", "The assigned executive records the field outcome and follow-up", 403)
            if not item.accepted_at:
                fail("accept_first", "The field executive must accept this handoff first", 409)
            if data.action == "visit_outcome":
                if visit.status != "scheduled" or data.visit_status is None:
                    fail("visit_not_ready", "This visit is no longer awaiting an outcome. Refresh the handoff", 409)
                recorded_at = now()
                if data.visit_status == "no-show" and visit.starts_at > recorded_at:
                    fail("visit_not_ready", "A no-show can only be recorded once the scheduled visit starts", 409)
                if data.visit_status == "completed":
                    if visit.starts_at > recorded_at and not data.early_visit_confirmed:
                        fail(
                            "early_visit_confirmation_required",
                            "If the client attended early, confirm the early visit and enter its actual date and time",
                            409,
                        )
                    if data.early_visit_confirmed:
                        if not data.actual_started_at:
                            fail("actual_visit_time_required", "Enter when the early visit actually took place", 422)
                        if data.actual_started_at > recorded_at or data.actual_started_at >= visit.starts_at:
                            fail(
                                "invalid_actual_visit_time",
                                "The actual early visit time must be in the past and before the scheduled visit",
                                422,
                            )
                        visit.actual_started_at = data.actual_started_at
                    elif data.actual_started_at:
                        fail(
                            "early_visit_confirmation_required",
                            "Confirm that the visit happened before the scheduled time",
                            422,
                        )
                if data.visit_status == "no-show" and data.next_step == "ready_for_booking":
                    fail("invalid_next_step", "A no-show needs follow-up or closure", 422)
                visit.status, visit.feedback = data.visit_status, data.feedback
            elif visit.status == "scheduled":
                fail("visit_pending", "Record or cancel the scheduled visit before closing or following up", 409)
            if data.action == "close":
                data.next_step = "closed"
            next_step(db, ctx, item, data)
        elif data.action == "cancel":
            if not (coordinator or executive):
                fail("permission_denied", "Only this handoff's team can cancel it", 403)
            if visit.status == "scheduled":
                visit.status, visit.feedback = "cancelled", data.feedback
            finish_task(db, item, "cancelled")
            item.status, item.follow_up_at, item.next_action = "cancelled", None, ""
        item.feedback = data.feedback
    item.updated_at, item.version = now(), item.version + 1
    audit(
        db,
        ctx,
        "lead",
        item.lead_id,
        "field_handoff_" + data.action,
        "Field work: " + data.action.replace("_", " "),
        {
            "handoff_id": item.id,
            "executive_id": item.executive_id,
            "status": item.status,
            "feedback": data.feedback,
            **(
                {
                    "visit_id": visit.id,
                    "scheduled_starts_at": visit.starts_at.isoformat(),
                    "actual_started_at": visit.actual_started_at.isoformat() if visit.actual_started_at else None,
                    "early_visit_confirmed": data.early_visit_confirmed,
                }
                if data.action == "visit_outcome"
                else {}
            ),
        },
    )
    return handoff_dump(db, item)
