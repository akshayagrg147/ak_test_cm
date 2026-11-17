"""Company message templates for WhatsApp click-to-chat and SMS links.

ViaCRM only renders text and logs that a chat was *opened*. It never sends, schedules or reads
messages, and there is no WhatsApp API or bulk action.
"""

import re
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .common import audit, dump, get_scoped, lead_access, mutate, rows
from .db import get_db, now
from .models import Audit, MessageTemplate, Organization, Note, Property, SiteVisit, User
from .schemas import Payload
from .security import current, fail, roles, workspace

router = APIRouter(prefix="/api", tags=["Message templates"])
PLACEHOLDERS = {
    "client_name",
    "first_name",
    "my_name",
    "company",
    "property_title",
    "property_price",
    "property_locality",
    "visit_time",
    "property_link",
}
PURPOSES = ("any", "new_lead", "follow_up", "site_visit", "property")
MAX_ACTIVE = 30
MAX_TEXT = 1000  # rendered and logged text limit; the preview is clamped so the log never rejects it
TOKEN = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
STARTERS = [
    ("Introduction", "new_lead",
     "Namaste {{first_name}} ji, main {{my_name}}, {{company}} se. Aapki property enquiry mili. Kab baat kar sakte hain?"),
    ("Site visit confirm", "site_visit",
     "{{first_name}} ji, site visit confirm: {{property_title}}, {{visit_time}}. Location bhej raha/rahi hoon."),
    ("Call not answered", "follow_up",
     "{{first_name}} ji, aapka phone nahi lag paaya. Aap free ho toh bataiye, call kar leta/leti hoon."),
    ("Property details", "property",
     "{{property_title}}, {{property_locality}}, {{property_price}}. Details: {{property_link}}"),
]


class TemplateIn(Payload):
    name: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=1000)
    purpose: Literal["any", "new_lead", "follow_up", "site_visit", "property"] = "any"
    active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)


class TemplateUpdate(Payload):
    """Partial edit: fields left out keep their saved values."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    body: str | None = Field(default=None, min_length=1, max_length=1000)
    purpose: Literal["any", "new_lead", "follow_up", "site_visit", "property"] | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1000)


def check_placeholders(body):
    unknown = sorted({name for name in TOKEN.findall(body) if name not in PLACEHOLDERS})
    if unknown:
        fail("unknown_placeholder",
             "Unknown placeholder " + ", ".join("{{" + n + "}}" for n in unknown)
             + ". Use: " + ", ".join("{{" + n + "}}" for n in sorted(PLACEHOLDERS)), 422)
    if "{{" in TOKEN.sub("", body) or "}}" in TOKEN.sub("", body):
        fail("unclosed_placeholder", "Close every placeholder with double curly brackets, for example {{first_name}}", 422)


class RenderIn(Payload):
    template_id: str = Field(min_length=1, max_length=36)
    property_id: str | None = Field(default=None, max_length=36)


class LogIn(Payload):
    channel: Literal["whatsapp", "sms"]
    template_id: str | None = Field(default=None, max_length=36)
    text: str = Field(min_length=1, max_length=MAX_TEXT)


def ensure_starter_templates(db, org_id, creator_id=None, force=False):
    """Give a company the starter templates once, ever: later setup runs never re-add deleted ones.

    `force` is only for the fictional Demo Realty reset, which rebuilds its own records.
    """
    org = db.get(Organization, org_id)
    seeded = org.settings.get("starter_templates_seeded", False)
    existing = db.scalar(select(func.count()).select_from(MessageTemplate).where(MessageTemplate.org_id == org_id))
    if not seeded:
        org.settings = {**org.settings, "starter_templates_seeded": True}
    if (seeded and not force) or existing:
        return
    for position, (name, purpose, body) in enumerate(STARTERS):
        db.add(MessageTemplate(org_id=org_id, name=name, purpose=purpose, body=body, sort_order=position,
                               created_by=creator_id, updated_at=now()))


def template_dump(item):
    return {k: v for k, v in dump(item).items() if k != "deleted"}


def visible_templates(db, ctx):
    query = rows(db, MessageTemplate, ctx.org_id).where(MessageTemplate.deleted.is_(False))
    if ctx.role not in {"admin", "manager"}:
        query = query.where(MessageTemplate.active.is_(True))
    return query.order_by(MessageTemplate.sort_order, func.lower(MessageTemplate.name))


@router.get("/message-templates")
def list_templates(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    return {"items": [template_dump(t) for t in db.scalars(visible_templates(db, ctx))],
            "placeholders": sorted(PLACEHOLDERS)}


def _check(db, ctx, data, existing=None):
    check_placeholders(data.body)
    duplicate = db.scalar(
        rows(db, MessageTemplate, ctx.org_id).where(
            MessageTemplate.deleted.is_(False),
            func.lower(MessageTemplate.name) == data.name.lower(),
            *([MessageTemplate.id != existing.id] if existing else []),
        )
    )
    if duplicate:
        fail("duplicate_name", "A template with this name already exists", 409)
    if data.active and not (existing and existing.active):
        active = db.scalar(
            select(func.count()).select_from(
                rows(db, MessageTemplate, ctx.org_id)
                .where(MessageTemplate.deleted.is_(False), MessageTemplate.active.is_(True))
                .subquery()
            )
        )
        if active >= MAX_ACTIVE:
            fail("template_limit", f"A company can keep up to {MAX_ACTIVE} active templates", 409)


@router.post("/message-templates", status_code=201)
def add_template(data: TemplateIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    _check(db, ctx, data)
    item = MessageTemplate(org_id=ctx.org_id, created_by=ctx.id, updated_at=now(), **data.model_dump())
    db.add(item)
    db.flush()
    audit(db, ctx, "message_template", item.id, "created", f"Added message template {item.name}")
    return template_dump(item)


def _template(db, ctx, template_id):
    item = get_scoped(db, MessageTemplate, template_id, ctx)
    if item.deleted:
        fail("not_found", "This record was not found", 404)
    return item


@router.put("/message-templates/{template_id}")
def edit_template(
    template_id: str, data: TemplateUpdate, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    item = _template(db, ctx, template_id)
    changes = data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        fail("invalid_value", "Fields cannot be null", 422)
    merged = TemplateIn(**{**{k: getattr(item, k) for k in TemplateIn.model_fields}, **changes})
    _check(db, ctx, merged, item)
    for key, value in changes.items():
        setattr(item, key, value)
    item.updated_at = now()
    audit(db, ctx, "message_template", item.id, "updated", f"Updated message template {item.name}")
    return template_dump(item)


@router.delete("/message-templates/{template_id}")
def delete_template(template_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    item = _template(db, ctx, template_id)
    used = db.scalar(
        select(Audit.id).where(
            Audit.org_id == ctx.org_id, Audit.action == "message_opened",
            Audit.details["template_id"].as_string() == item.id,
        ).limit(1)
    )
    if used:
        item.active, item.deleted = False, True
    else:
        db.delete(item)
    audit(db, ctx, "message_template", template_id, "removed",
          f"Removed message template {item.name}" + (" (kept for activity history)" if used else ""))
    return {"ok": True, "kept_for_history": bool(used)}


def contactable_lead(db, ctx, lead_id):
    """The lead must be visible to the user and not do-not-contact.

    Archived (deleted) leads are already 404 through lead_access. Won and lost clients stay messageable:
    the owner chose on 17 Nov 2026 to keep WhatsApp available for them.
    """
    lead = lead_access(db, ctx, lead_id)
    if lead.dnd:
        fail("do_not_contact", "Client is marked do-not-contact", 409)
    return lead


TITLES = re.compile(r"^(mr|mrs|ms|miss|dr|shri|sri|smt|kumari)\.?$", re.IGNORECASE)


def address_name(full_name):
    """First word of the name that isn't a title such as "Mr." or "Smt." (same rule as the WhatsApp button)."""
    words = full_name.split()
    return next((w for w in words if not TITLES.match(w)), words[0] if words else "")


def indian_price(value):
    amount = Decimal(value or 0)
    if amount >= 10_000_000:
        return "₹" + f"{amount / 10_000_000:.2f}".rstrip("0").rstrip(".") + " Cr"
    if amount >= 100_000:
        return "₹" + f"{amount / 100_000:.2f}".rstrip("0").rstrip(".") + " L"
    whole = str(int(amount))
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1] if len(head) > 2 else head
        whole = head + "," + tail
    return "₹" + whole


def visit_label(moment, zone):
    local = moment.astimezone(zone)
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local:%a} {local.day} {local:%b}, {hour}:{local:%M} {local:%p}".replace("AM", "am").replace("PM", "pm")


def tidy(text):
    """Remove gaps left by blank placeholders: doubled spaces, empty commas and space before punctuation."""
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]{2,}", " ", line)
        line = re.sub(r"\s+([,.!?:])", r"\1", line)
        line = re.sub(r",(\s*,)+", ",", line)
        previous = None
        while previous != line:
            previous = line
            line = re.sub(r"([:,])(?=[:,.!?]|$)", "", line.rstrip())
        line = re.sub(r"^[\s,]+", "", line)
        lines.append(line.strip())
    return "\n".join(lines).strip()


@router.post("/leads/{lead_id}/template-render")
def render_template(lead_id: str, data: RenderIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    lead = contactable_lead(db, ctx, lead_id)
    template = _template(db, ctx, data.template_id)
    if not template.active:
        fail("not_found", "This template is no longer available; pick another", 404)
    prop = None
    if data.property_id:
        prop = get_scoped(db, Property, data.property_id, ctx)
        if prop.archived or prop.status != "available":
            fail("property_unavailable", "This property is no longer available", 409)
    zone = ZoneInfo(ctx.org.settings.get("workplace", {}).get("timezone", "Asia/Kolkata"))
    visit = db.scalar(
        rows(db, SiteVisit, ctx.org_id)
        .where(SiteVisit.lead_id == lead.id, SiteVisit.status == "scheduled", SiteVisit.starts_at >= now())
        .order_by(SiteVisit.starts_at)
        .limit(1)
    )
    me = db.get(User, ctx.id)
    values = {
        "client_name": lead.name.strip(),
        "first_name": address_name(lead.name),
        "my_name": me.name if me else "",
        "company": ctx.org.settings.get("brand_name") or ctx.org.name,
        "property_title": prop.title if prop else "",
        "property_price": indian_price(prop.price) if prop else "",
        "property_locality": prop.locality if prop else "",
        "visit_time": visit_label(visit.starts_at, zone) if visit else "",
        "property_link": "",
    }
    used = [name for name in TOKEN.findall(template.body) if name in PLACEHOLDERS]
    missing = sorted({name for name in used if not values[name]})
    text = tidy(TOKEN.sub(lambda m: values.get(m.group(1), ""), template.body))
    truncated = len(text) > MAX_TEXT
    return {"text": text[:MAX_TEXT].rstrip(), "missing": missing, "truncated": truncated,
            "template_id": template.id, "template_name": template.name}


@router.post("/leads/{lead_id}/message-log", status_code=201)
def log_message(lead_id: str, data: LogIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    lead = contactable_lead(db, ctx, lead_id)
    template = _template(db, ctx, data.template_id) if data.template_id else None
    if template and not template.active:
        fail("not_found", "This template is no longer available; pick another", 404)
    label = "WhatsApp" if data.channel == "whatsapp" else "SMS"
    heading = f"{label} message opened" + (f" using template {template.name}" if template else "")
    note = Note(org_id=ctx.org_id, lead_id=lead.id, author_id=ctx.id, text=heading + "\n\n" + data.text)
    db.add(note)
    db.flush()
    audit(db, ctx, "lead", lead.id, "message_opened", heading,
          {"channel": data.channel, "template_id": template.id if template else None, "note_id": note.id})
    return {"ok": True, "note_id": note.id}
