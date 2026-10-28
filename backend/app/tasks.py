from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .common import audit, dump, event, get_scoped, lead_access, member, mutate, rows, visible_lead_ids
from .db import get_db, now
from .models import Task
from .schemas import TaskIn
from .security import current, fail, workspace

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def task_access(db, ctx, task_id):
    task = get_scoped(db, Task, task_id, ctx)
    if ctx.role in {"telecaller", "field_executive"}:
        if task.owner_id != ctx.id:
            fail("not_found", "Task not found", 404)
        if task.lead_id:
            lead_access(db, ctx, task.lead_id)
    return task


@router.get("")
def list_tasks(
    state: str | None = None,
    owner_id: str | None = None,
    kind: str | None = None,
    priority: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    workspace(ctx)
    if any(value and value.tzinfo is None for value in [from_date, to_date]):
        fail("timezone_required", "Include timezones in task date filters", 422)
    if from_date and to_date and from_date >= to_date:
        fail("invalid_date_range", "The end must be after the start", 422)
    query = rows(db, Task, ctx.org_id)
    if ctx.role in {"telecaller", "field_executive"}:
        allowed_leads = visible_lead_ids(ctx)
        query = query.where(Task.owner_id == ctx.id, (Task.lead_id.is_(None)) | (Task.lead_id.in_(allowed_leads)))
    for column, value in [(Task.state, state), (Task.owner_id, owner_id), (Task.kind, kind), (Task.priority, priority)]:
        if value:
            query = query.where(column == value)
    if from_date:
        query = query.where(Task.due_at >= from_date)
    if to_date:
        query = query.where(Task.due_at < to_date)
    from .field_work import linked_handoff
    result = []
    for task in db.scalars(query.order_by(Task.due_at, Task.id).offset((page - 1) * 100).limit(100)):
        handoff = linked_handoff(db, ctx.org_id, task_id=task.id)
        result.append({**dump(task), "field_handoff_id": handoff.id if handoff else None})
    return result


def validate_task(db, ctx, data):
    owner_id = data.owner_id or ctx.id
    if ctx.role in {"telecaller", "field_executive"} and owner_id != ctx.id:
        fail("permission_denied", "You can only own your own tasks", 403)
    member(db, ctx, owner_id)
    if data.lead_id:
        lead = lead_access(db, ctx, data.lead_id)
        owner = member(db, ctx, owner_id)
        if owner.role == "telecaller" and lead.owner_id != owner_id:
            fail("invalid_task_owner", "A telecaller task must use a lead currently assigned to them", 422)
        if owner.role == "field_executive" and lead.owner_id != owner_id:
            from .models import FieldHandoff
            if not db.scalar(rows(db, FieldHandoff, ctx.org_id).where(
                FieldHandoff.lead_id == lead.id, FieldHandoff.executive_id == owner_id, FieldHandoff.current.is_(True)
            )):
                fail("invalid_task_owner", "Choose the field executive responsible for this lead", 422)
    return owner_id


@router.post("", status_code=201)
def create_task(data: TaskIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    owner = validate_task(db, ctx, data)
    task = Task(
        org_id=ctx.org_id,
        creator_id=ctx.id,
        **{**data.model_dump(), "owner_id": owner},
        completed_at=now() if data.state == "completed" else None,
    )
    db.add(task)
    db.flush()
    audit(db, ctx, "task", task.id, "created", f"Created task {task.title}")
    if task.state == "completed" and task.lead_id:
        event(db, ctx.org_id, "task_completed", task.lead_id, ctx.id)
    return dump(task)


@router.put("/{task_id}")
def edit_task(task_id: str, data: TaskIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    task = task_access(db, ctx, task_id)
    from .field_work import linked_handoff
    if linked_handoff(db, ctx.org_id, task_id=task_id):
        fail("field_task_managed", "Update this follow-up in Field work to keep the client's next step consistent", 409)
    owner = validate_task(db, ctx, data)
    previous = task.state
    for key, value in {**data.model_dump(), "owner_id": owner}.items():
        setattr(task, key, value)
    task.completed_at = (
        now()
        if task.state == "completed" and previous != "completed"
        else task.completed_at
        if task.state == "completed"
        else None
    )
    if task.state == "completed" and previous != "completed" and task.lead_id:
        event(db, ctx.org_id, "task_completed", task.lead_id, ctx.id)
    audit(db, ctx, "task", task.id, "updated", f"Updated task {task.title}")
    return dump(task)


@router.delete("/{task_id}")
def delete_task(task_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    task = task_access(db, ctx, task_id)
    from .field_work import linked_handoff
    if linked_handoff(db, ctx.org_id, task_id=task_id):
        fail("field_task_managed", "Update or close this follow-up in Field work", 409)
    audit(db, ctx, "task", task.id, "deleted", f"Removed task {task.title}")
    db.delete(task)
    return {"ok": True}
