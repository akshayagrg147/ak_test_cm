"""Live, permission-scoped reminders; opening the bell never resolves work."""

from datetime import timedelta, timezone
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, false, func, literal, select, union_all
from sqlalchemy.orm import Session

from .common import rows, visible_lead_ids
from .db import get_db, now
from .field_work import handoff_query
from .leads import lead_query
from .models import Definition, FieldHandoff, Lead, Task, User
from .security import current, workspace

router = APIRouter(prefix="/api/notifications", tags=["Alerts & reminders"])


def columns(identifier, kind, title, description, url, due_at, priority, lead_id, owner_id):
    return [
        identifier.label("id"),
        kind.label("kind"),
        title.label("title"),
        description.label("description"),
        url.label("url"),
        due_at.label("due_at"),
        priority.label("priority"),
        lead_id.label("lead_id"),
        owner_id.label("owner_id"),
    ]


def inbox_query(db, ctx, stamp):
    workspace(ctx)
    closed = {"won", "lost"} | {
        stage.key
        for stage in db.scalars(rows(db, Definition, ctx.org_id).where(Definition.kind == "stage"))
        if stage.config.get("closed", False)
    }
    eligible = lead_query(ctx).where(
        Lead.dnd.is_(False), Lead.status.notin_(["lost", "converted"]), Lead.stage.notin_(closed)
    )
    callbacks = eligible.where(Lead.follow_up <= stamp).with_only_columns(
        *columns(
            literal("callback-") + Lead.id,
            literal("callback"),
            literal("Callback overdue"),
            Lead.name,
            literal("/app/leads/") + Lead.id,
            Lead.follow_up,
            literal(0),
            Lead.id,
            Lead.owner_id,
        )
    )
    first_contact = eligible.where(
        Lead.follow_up.is_(None), Lead.last_contact.is_(None), Lead.created_at <= stamp - timedelta(hours=48)
    ).with_only_columns(
        *columns(
            literal("first-") + Lead.id,
            literal("first_contact"),
            literal("First contact needed"),
            Lead.name,
            literal("/app/leads/") + Lead.id,
            Lead.created_at + timedelta(hours=48),
            literal(4),
            Lead.id,
            Lead.owner_id,
        )
    )
    field_task = (
        select(FieldHandoff.id)
        .where(
            FieldHandoff.org_id == ctx.org_id,
            FieldHandoff.task_id == Task.id,
            FieldHandoff.current.is_(True),
        )
        .exists()
    )
    is_callback = and_(Task.kind == "callback", Task.due_at <= stamp)
    tasks = (
        rows(db, Task, ctx.org_id)
        .where(
            Task.owner_id == ctx.id,
            Task.state == "open",
            Task.due_at <= stamp + timedelta(days=1),
            (Task.lead_id.is_(None)) | Task.lead_id.in_(visible_lead_ids(ctx)),
            (Task.kind != "callback") | Task.lead_id.is_(None) | Task.lead_id.in_(eligible.with_only_columns(Lead.id)),
        )
        .with_only_columns(
            *columns(
                literal("task-") + Task.id,
                case((is_callback, "callback"), else_="task"),
                case(
                    (and_(is_callback, field_task), "Field follow-up overdue"),
                    (is_callback, "Callback task overdue"),
                    (Task.due_at <= stamp, "Task overdue"),
                    else_="Task due soon",
                ),
                Task.title,
                case((field_task, literal("/app/leads/") + Task.lead_id), else_="/app/tasks"),
                Task.due_at,
                case((is_callback, 0), (Task.due_at <= stamp, 2), else_=3),
                Task.lead_id,
                Task.owner_id,
            )
        )
    )
    allowed_field = ctx.role in {"admin", "manager", "field_executive"}
    target = "pending" if ctx.role == "field_executive" else "ready_for_booking"
    handoffs = (
        handoff_query(ctx)
        .where(
            FieldHandoff.current.is_(True),
            FieldHandoff.status == target,
            literal(True) if allowed_field else false(),
        )
        .with_only_columns(
            *columns(
                literal("field-") + FieldHandoff.id,
                literal("handoff"),
                literal("Accept client handoff" if ctx.role == "field_executive" else "Client ready for booking"),
                Lead.name,
                literal("/app/leads/") + Lead.id,
                FieldHandoff.created_at,
                literal(1),
                Lead.id,
                FieldHandoff.executive_id,
            )
        )
    )
    return union_all(callbacks, tasks, handoffs, first_contact).subquery()


@router.get("/inbox")
def inbox(
    category: Literal["all", "callbacks"] = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    stamp = now()
    query = inbox_query(db, ctx, stamp)
    grouped = dict(db.execute(select(query.c.kind, func.count()).group_by(query.c.kind)).all())
    all_count = sum(grouped.values())
    callback_count = grouped.get("callback", 0)
    total = callback_count if category == "callbacks" else all_count
    pages = max(1, ceil(total / page_size))
    page = min(page, pages)
    selected = select(query)
    if category == "callbacks":
        selected = selected.where(query.c.kind == "callback")
    items = [
        dict(row)
        for row in db.execute(
            selected.order_by(query.c.priority, query.c.due_at, query.c.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings()
    ]
    members = {
        user.id: user.name
        for user in db.scalars(rows(db, User, ctx.org_id).where(User.id.in_([item["owner_id"] for item in items])))
    }
    for item in items:
        item["due_at"] = item["due_at"].astimezone(timezone.utc).isoformat()
        item["owner_name"] = members.get(item.pop("owner_id"), "Unassigned")
        item.pop("priority")
    return {
        "items": items,
        "counts": {"callbacks": callback_count, "other": all_count - callback_count, "all": all_count},
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "as_of": stamp.isoformat(),
        "timezone": ctx.org.settings.get("workplace", {}).get("timezone", "Asia/Kolkata"),
    }
