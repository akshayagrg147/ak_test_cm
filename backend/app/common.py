import csv
import io
from datetime import date
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy import or_, select

from .models import Assignment, Audit, Definition, FieldHandoff, Job, Lead, User
from .security import check_current, fail, lock_org, workspace

SENSITIVE = {"password_hash", "totp_secret", "totp_last_step", "refresh_hash", "secret", "storage_key"}


def dump(obj):
    if obj is None:
        return None
    return jsonable_encoder(
        {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name not in SENSITIVE},
        custom_encoder={Decimal: str},
    )


def rows(db, cls, org_id):
    return select(cls).where(cls.org_id == org_id)


def get_scoped(db, cls, entity_id, ctx):
    workspace(ctx)
    obj = db.scalar(rows(db, cls, ctx.org_id).where(cls.id == entity_id))
    if not obj:
        fail("not_found", "This record was not found", 404)
    return obj


def mutate(db, ctx):
    workspace(ctx)
    lock_org(db, ctx.org_id)
    db.refresh(ctx.user)
    db.refresh(ctx.session)
    fresh = check_current(db, ctx.session)
    ctx.role = fresh.role


def member(db, ctx, user_id, role=None):
    obj = get_scoped(db, User, user_id, ctx)
    if not obj.active or obj.deleted or (role and obj.role != role):
        fail("invalid_member", f"Choose an active {role or 'member'} in this organization", 422)
    return obj


def lead_condition(ctx):
    if ctx.role == "telecaller":
        return Lead.owner_id == ctx.id
    if ctx.role == "field_executive":
        return or_(Lead.owner_id == ctx.id, Lead.id.in_(
            select(FieldHandoff.lead_id).where(
                FieldHandoff.org_id == ctx.org_id, FieldHandoff.executive_id == ctx.id, FieldHandoff.current.is_(True)
            )
        ))
    return True


def visible_lead_ids(ctx):
    return select(Lead.id).where(Lead.org_id == ctx.org_id, Lead.deleted.is_(False), lead_condition(ctx))


def lead_access(db, ctx, lead_id):
    lead = get_scoped(db, Lead, lead_id, ctx)
    if lead.deleted or not db.scalar(select(Lead.id).where(Lead.id == lead.id, lead_condition(ctx))):
        fail("not_found", "This lead is not available to you", 404)
    return lead


def audit(db, ctx, entity, entity_id, action, summary, details=None):
    db.add(
        Audit(
            org_id=ctx.org_id,
            actor_id=ctx.actor_id,
            entity=entity,
            entity_id=entity_id,
            action=action,
            summary=summary,
            details={**(details or {}), **({"acting_as_user_id": ctx.id} if ctx.session.acting_user_id else {})},
        )
    )


def event(db, org_id, trigger, lead_id, actor_id, key=None):
    from .db import uid

    db.add(
        Job(
            org_id=org_id,
            kind="automation",
            key=key or uid(),
            payload={"trigger": trigger, "lead_id": lead_id, "actor_id": actor_id},
        )
    )


def assign(db, ctx, lead, owner_id, source="manual", automate=True):
    previous = lead.owner_id
    if previous == owner_id:
        return
    lead.owner_id = owner_id
    db.add(
        Assignment(
            org_id=ctx.org_id, lead_id=lead.id, previous_id=previous, owner_id=owner_id, actor_id=ctx.id, source=source
        )
    )
    audit(
        db,
        ctx,
        "lead",
        lead.id,
        "assigned",
        "Lead ownership updated",
        {"previous_id": previous, "owner_id": owner_id, "source": source},
    )
    if automate:
        event(db, ctx.org_id, "lead_assigned", lead.id, ctx.id)


DEFAULT_CATEGORIES = ["pharmaceutical", "ayurvedic", "homeopathic", "nutraceutical", "generic", "other"]
REAL_ESTATE_CATEGORIES = ["apartment", "villa", "plot", "office", "retail", "warehouse", "other"]
HEALTHCARE_DEFAULT_CATEGORIES = set(DEFAULT_CATEGORIES) - {"other"}


def retire_healthcare_defaults(db, org_id):
    """Keep historical definitions and customer values; retire unchanged industry seeds."""
    for definition in db.scalars(
        rows(db, Definition, org_id).where(
            Definition.kind == "category", Definition.key.in_(HEALTHCARE_DEFAULT_CATEGORIES)
        )
    ):
        if definition.label.casefold() == definition.key:
            definition.active = False


def init_org(db, org):
    real_estate = org.settings.get("industry") == "real_estate"
    for pos, (key, label) in enumerate(
        [("new", "New enquiry"), ("qualified", "Qualified buyer"), ("site_visit", "Site visit"),
         ("proposal", "Negotiation"), ("won", "Booked"), ("lost", "Lost")]
        if real_estate else [("new", "New enquiry"), ("qualified", "Qualified"), ("proposal", "Proposal"), ("won", "Won"), ("lost", "Lost")]
    ):
        db.add(
            Definition(
                org_id=org.id,
                kind="stage",
                key=key,
                label=label,
                position=pos,
                config={"color": "#137b65", "closed": key in ["won", "lost"], "won": key == "won"},
            )
        )
    for pos, key in enumerate(REAL_ESTATE_CATEGORIES if real_estate else DEFAULT_CATEGORIES):
        db.add(Definition(org_id=org.id, kind="category", key=key, label=key.title(), position=pos))


def validate_lead(db, ctx, data):
    definitions = list(db.scalars(rows(db, Definition, ctx.org_id)))
    existing = db.get(Lead, data["id"]) if data.get("id") else None
    stages = {d.key for d in definitions if d.kind == "stage" and d.active}
    if data.get("stage", "new") not in stages:
        fail("invalid_stage", "Select an active pipeline stage", 422)
    categories = {d.key for d in definitions if d.kind == "category" and d.active}
    if existing:
        categories.add(existing.category)
    if data.get("category") and data["category"] not in categories:
        fail("invalid_category", "Select a configured primary category", 422)
    values = data.get("custom", {})
    fields = {d.key: d for d in definitions if d.kind == "field"}
    if set(values) - fields.keys():
        fail("unknown_custom_field", "Custom fields contain unrecognized keys", 422)
    for key, d in fields.items():
        v = values.get(key)
        if not d.active:
            if (existing and key in existing.custom and (key not in values or v != existing.custom[key])) or (
                key in values and (not existing or key not in existing.custom)
            ):
                fail("inactive_custom_field", f"{d.label} is inactive and cannot be changed", 422)
            continue
        if d.config.get("required") and (v is None or v == ""):
            fail("required_custom_field", f"{d.label} is required", 422)
        if v is None or v == "":
            continue
        kind = d.config.get("type", "text")
        valid = True
        if kind == "number":
            valid = type(v) in [int, float] and abs(v) < 1e14
        elif kind == "boolean":
            valid = type(v) is bool
        elif kind == "date":
            try:
                date.fromisoformat(v)
            except Exception:
                valid = False
        elif kind == "select":
            valid = v in d.config.get("options", []) or bool(
                existing and key in existing.custom and existing.custom[key] == v
            )
        else:
            valid = isinstance(v, str) and len(v) <= 2000
        if not valid:
            fail("invalid_custom_field", f"Invalid value for {d.label}", 422)
    details = data.get("details", {})
    if set(details) - {"drug_license", "specialty", "credit_limit", "outstanding"}:
        fail("invalid_details", "Unsupported qualification field", 422)
    for key in ["credit_limit", "outstanding"]:
        if key in details:
            try:
                amount = Decimal(str(details[key]))
                if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
                    raise ValueError()
            except Exception:
                fail("invalid_amount", f"{key} must be a nonnegative amount", 422)
    if len(str(details)) > 4000:
        fail("invalid_details", "Qualification details are too long", 422)


def score(lead):
    factors = {
        "Contact details": 20,
        "Location": 10 if lead.city else 0,
        "Interests recorded": 15 if any(isinstance(item, str) and item.strip() for item in lead.interests) else 0,
        "Contact made": 15 if lead.last_contact else 0,
        "Next step scheduled": 15 if lead.follow_up else 0,
        "Pipeline progress": 25
        if lead.stage in ["proposal", "won"] or lead.status == "converted"
        else 10
        if lead.stage == "qualified"
        else 0,
    }
    value = sum(factors.values())
    return {"value": value, "band": "hot" if value >= 75 else "warm" if value >= 45 else "cool", "factors": factors}


def lead_dump(db, lead):
    result = dump(lead)
    result["score"] = score(lead)
    result["owner_name"] = db.get(User, lead.owner_id).name if lead.owner_id else "Unassigned"
    return result


def csv_response(items, fields, name="export.csv"):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(fields)
    for item in items:
        values = []
        for key in fields:
            value = item.get(key, "")
            text = "" if value is None else str(value)
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                text = "'" + text
            values.append(text)
        writer.writerow(values)
    return Response(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
