import json
import re

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .common import audit, csv_response, dump, get_scoped, member, mutate, rows
from .config import settings
from .db import Base, get_db
from .files import store
from .models import Audit, Automation, AutomationRun, Backup, Definition, Lead, SavedView
from .schemas import AutomationIn, DefinitionIn, SettingsIn, ViewIn
from .security import current, fail, roles, workspace

router = APIRouter(prefix="/api", tags=["Workspace configuration"])


@router.get("/settings")
def get_settings(ctx=Depends(current)):
    workspace(ctx)
    return {"name": ctx.org.name, "settings": ctx.org.settings}


@router.put("/settings")
def put_settings(data: SettingsIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    values = data.model_dump(mode="json", exclude_none=True)
    name = values.pop("name", None)
    if name:
        ctx.org.name = name
    if ctx.org.settings.get("industry") == "real_estate":
        values["pharma_enabled"] = False
    # Logo is managed by the private-file endpoint.
    ctx.org.settings = {
        **ctx.org.settings,
        **values,
        **({"logo_id": ctx.org.settings["logo_id"]} if ctx.org.settings.get("logo_id") else {}),
    }
    audit(db, ctx, "organization", ctx.org_id, "settings_updated", "Workspace settings updated")
    return dump(ctx.org)


@router.get("/definitions")
def definitions(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    return [
        dump(r)
        for r in db.scalars(
            rows(db, Definition, ctx.org_id).order_by(Definition.kind, Definition.position, Definition.label)
        )
    ]


def validate_definition(data):
    config = data.config
    if data.kind == "field":
        if set(config) - {"type", "required", "options"} or config.get("type") not in [
            "text",
            "number",
            "boolean",
            "date",
            "select",
        ]:
            fail("invalid_field", "Field type must be text, number, boolean, date or select", 422)
        if type(config.get("required", False)) is not bool:
            fail("invalid_field", "Required must be true or false", 422)
        if config.get("type") == "select" and (
            not isinstance(config.get("options"), list)
            or not config["options"]
            or len(config["options"]) > 100
            or any(not isinstance(x, str) or not x.strip() or x != x.strip() or len(x) > 100 for x in config["options"])
            or len(set(config["options"])) != len(config["options"])
        ):
            fail("invalid_options", "Select fields require unique text options", 422)
    elif data.kind == "stage":
        if set(config) - {"color", "closed", "won"} or not re.fullmatch(
            r"#[0-9a-fA-F]{6}", config.get("color", "#137b65")
        ):
            fail("invalid_stage", "Use a six-digit hex color and closed/won flags", 422)
        if any(type(config.get(key, False)) is not bool for key in ["closed", "won"]):
            fail("invalid_stage", "Closed and won must be boolean", 422)
        if config.get("won") and not config.get("closed"):
            fail("invalid_stage", "Won stages must also be closed", 422)
    elif config:
        fail("invalid_category", "Categories do not accept configuration properties", 422)


@router.post("/definitions", status_code=201)
def add_definition(data: DefinitionIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    validate_definition(data)
    if db.scalar(rows(db, Definition, ctx.org_id).where(Definition.kind == data.kind, Definition.key == data.key)):
        fail("duplicate_key", "This definition key already exists", 409)
    record = Definition(org_id=ctx.org_id, **data.model_dump())
    db.add(record)
    db.flush()
    audit(db, ctx, "definition", record.id, "created", f"Created {data.kind}: {data.label}")
    return dump(record)


@router.put("/definitions/{record_id}")
def edit_definition(
    record_id: str, data: DefinitionIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin")
    mutate(db, ctx)
    record = get_scoped(db, Definition, record_id, ctx)
    validate_definition(data)
    if data.kind != record.kind or data.key != record.key:
        fail("immutable_key", "Definition keys and types cannot change; create a new definition", 422)
    if record.kind == "stage" and record.key in ["new", "qualified", "won", "lost"]:
        if (
            not data.active
            or data.config.get("closed", False) != (record.key in ["won", "lost"])
            or data.config.get("won", False) != (record.key == "won")
        ):
            fail(
                "system_stage",
                "Default status-mapping stages must remain active with their original closed/won meaning",
                409,
            )
    if (
        not data.active
        and record.kind == "stage"
        and db.scalar(rows(db, Lead, ctx.org_id).where(Lead.stage == record.key, Lead.deleted.is_(False)))
    ):
        fail("stage_in_use", "Move leads to another stage before deactivating this stage", 409)
    for key, value in data.model_dump().items():
        setattr(record, key, value)
    audit(db, ctx, "definition", record.id, "updated", f"Updated {data.label}")
    return dump(record)


@router.delete("/definitions/{record_id}")
def delete_definition(
    record_id: str, migrate_to: str | None = None, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin")
    mutate(db, ctx)
    record = get_scoped(db, Definition, record_id, ctx)
    if record.kind == "stage":
        if record.key in ["new", "qualified", "won", "lost"]:
            fail("system_stage", "Default status-mapping stages cannot be removed", 409)
        leads = list(db.scalars(rows(db, Lead, ctx.org_id).where(Lead.stage == record.key, Lead.deleted.is_(False))))
        if leads and not migrate_to:
            fail("stage_in_use", "Choose a destination stage to migrate existing leads", 409)
        if leads:
            destination = db.scalar(
                rows(db, Definition, ctx.org_id).where(
                    Definition.kind == "stage",
                    Definition.key == migrate_to,
                    Definition.active.is_(True),
                    Definition.id != record.id,
                )
            )
            if not destination:
                fail("invalid_stage", "Choose another active stage", 422)
            for lead in leads:
                lead.stage = destination.key
                audit(
                    db, ctx, "lead", lead.id, "stage_migrated", f"Migrated stage from {record.key} to {destination.key}"
                )
    # Keep field/category definitions inactive so historical records stay interpretable.
    record.active = False
    audit(db, ctx, "definition", record.id, "deactivated", f"Deactivated {record.label}")
    return {"ok": True}


def validate_rule(db, ctx, data):
    if set(data.conditions) - {"status", "source", "category", "stage"} or any(
        not isinstance(v, str) for v in data.conditions.values()
    ):
        fail("invalid_conditions", "Conditions support exact status, source, category and stage values", 422)
    config = data.config
    if data.action == "assign_manager":
        member(db, ctx, config.get("manager_id", ""), "manager")
        if set(config) - {"manager_id"}:
            fail("invalid_action", "Assignment accepts only manager_id", 422)
    elif data.action == "create_task":
        if (
            set(config) - {"title", "delay_minutes"}
            or not isinstance(config.get("title"), str)
            or not 2 <= len(config["title"]) <= 200
            or type(config.get("delay_minutes", 0)) is not int
            or not 0 <= config.get("delay_minutes", 0) <= 525600
        ):
            fail("invalid_action", "Task actions require a title and a delay from 0 to 525600 minutes", 422)
    elif data.action == "add_note":
        if set(config) - {"text"} or not isinstance(config.get("text"), str) or not 1 <= len(config["text"]) <= 10000:
            fail("invalid_action", "Note actions require text of at most 10,000 characters", 422)


@router.get("/automations")
def automations(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin", "manager")
    return {
        "rules": [dump(r) for r in db.scalars(rows(db, Automation, ctx.org_id).order_by(Automation.created_at))],
        "runs": [
            dump(r)
            for r in db.scalars(
                rows(db, AutomationRun, ctx.org_id).order_by(AutomationRun.created_at.desc()).limit(100)
            )
        ],
    }


@router.post("/automations", status_code=201)
def add_rule(data: AutomationIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    validate_rule(db, ctx, data)
    rule = Automation(org_id=ctx.org_id, **data.model_dump())
    db.add(rule)
    db.flush()
    audit(db, ctx, "automation", rule.id, "created", f"Created rule {rule.name}")
    return dump(rule)


@router.put("/automations/{rule_id}")
def edit_rule(rule_id: str, data: AutomationIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    rule = get_scoped(db, Automation, rule_id, ctx)
    validate_rule(db, ctx, data)
    for key, value in data.model_dump().items():
        setattr(rule, key, value)
    audit(db, ctx, "automation", rule.id, "updated", f"Updated rule {rule.name}")
    return dump(rule)


@router.get("/saved-views")
def views(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    return [
        dump(r)
        for r in db.scalars(rows(db, SavedView, ctx.org_id).where(SavedView.user_id == ctx.id).order_by(SavedView.name))
    ]


@router.post("/saved-views", status_code=201)
def save_view(data: ViewIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    from .leads import filters

    allowed = set(filters.__annotations__) - {"return"}
    if data.kind == "analytics":
        allowed = {"from_date", "to_date", "owner_id"}
    if set(data.filters) - allowed or len(json.dumps(data.filters)) > 4000:
        fail("invalid_filters", "The view contains unsupported filters", 422)
    from datetime import date, datetime

    for key, value in data.filters.items():
        if (key == "dnd" and not isinstance(value, (str, bool))) or (key != "dnd" and not isinstance(value, str)):
            fail("invalid_filters", "Saved filter values must be text or booleans", 422)
        if key in ["from_date", "to_date"] and value:
            try:
                if len(value) == 10:
                    date.fromisoformat(value)
                elif datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                    raise ValueError()
            except Exception:
                fail("invalid_filters", "Saved date filters require a date or timezone-aware timestamp", 422)
    if data.filters.get("from_date") and data.filters.get("to_date"):
        start = datetime.fromisoformat(data.filters["from_date"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(data.filters["to_date"].replace("Z", "+00:00"))
        if start.tzinfo != end.tzinfo and (start.tzinfo is None or end.tzinfo is None):
            fail("invalid_filters", "Use matching date or timestamp formats", 422)
        if start >= end:
            fail("invalid_filters", "The end must be after the start", 422)
    view = SavedView(org_id=ctx.org_id, user_id=ctx.id, **data.model_dump())
    db.add(view)
    db.flush()
    return dump(view)


@router.delete("/saved-views/{record_id}")
def remove_view(record_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    record = get_scoped(db, SavedView, record_id, ctx)
    if record.user_id != ctx.id:
        fail("not_found", "View not found", 404)
    db.delete(record)
    return {"ok": True}


@router.get("/audit")
def audit_log(
    q: str = "",
    action: str | None = None,
    page: int = Query(1, ge=1),
    export: bool = False,
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    workspace(ctx)
    roles(ctx, "admin", "manager")
    query = rows(db, Audit, ctx.org_id)
    if q:
        query = query.where(Audit.summary.ilike(f"%{q[:100]}%"))
    if action:
        query = query.where(Audit.action == action)
    if ctx.role == "manager":
        query = query.where(Audit.entity.not_in(["pay_profile", "backup", "integration"]))
    items = [
        dump(r)
        for r in db.scalars(
            query.order_by(Audit.created_at.desc(), Audit.id)
            .offset(0 if export else (page - 1) * 50)
            .limit(10001 if export else 50)
        )
    ]
    if export and len(items) > 10000:
        fail("export_too_large", "Narrow the filters to at most 10,000 audit entries", 422)
    return (
        csv_response(items, ["created_at", "actor_id", "entity", "entity_id", "action", "summary"], "audit.csv")
        if export
        else items
    )


@router.get("/backups")
def backups(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin")
    return [dump(r) for r in db.scalars(rows(db, Backup, ctx.org_id).order_by(Backup.created_at.desc()))]


@router.post("/backups", status_code=201)
def snapshot(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    tables = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, "org_id") and cls.__tablename__ not in ["backups"]:
            tables[cls.__tablename__] = [dump(r) for r in db.scalars(select(cls).where(cls.org_id == ctx.org_id))]
    raw = json.dumps(
        {
            "format": "talkocrm-application-snapshot-v1",
            "organization": dump(ctx.org),
            "data": tables,
            "limitations": "Passwords, credentials, sessions and file bytes excluded. This is not a disaster-recovery backup.",
        },
        ensure_ascii=False,
    ).encode()
    record = Backup(org_id=ctx.org_id, author_id=ctx.id, storage_key=store(raw), size=len(raw))
    db.add(record)
    db.flush()
    audit(db, ctx, "backup", record.id, "created", "Created application JSON snapshot")
    return dump(record)


@router.get("/backups/{record_id}")
def download_snapshot(record_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    record = get_scoped(db, Backup, record_id, ctx)
    path = settings.storage_path / record.storage_key
    if not path.exists():
        fail("file_unavailable", "Snapshot file is missing", 404)
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"workspace-{record.created_at.date()}.json",
        headers={"Cache-Control": "private, no-store"},
    )
