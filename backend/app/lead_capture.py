"""Capture enquiries from a company's website, its hosted enquiry form and Google Ads lead forms.

Every channel shares one intake path: valid enquiries create a lead or are merged into the existing
lead with the same phone number, the enquiry time is recorded for speed-to-lead alerts, and new
leads can be assigned round-robin to active telecallers.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .common import audit, event, mutate, rows
from .config import settings
from .db import get_db, now, uid
from .models import Assignment, Audit, Integration, Lead, Organization, Provenance, SyncRun, User
from .schemas import Payload
from .security import current, decrypt, encrypt, fail, lock_org, phone, require_browser_request, roles, workspace

router = APIRouter(prefix="/api", tags=["Lead capture"])

# Integration provider -> lead source and the label used in notes and settings.
CHANNELS = {
    "website": ("website", "Website integration"),
    "google-ads": ("google-ads", "Google Ads lead form"),
    "website-form": ("website", "Website enquiry form"),
}
KEY_CHANNELS = ("website", "google-ads")
FORM_RATE_LIMIT = 30  # hosted-form enquiries per company per 10 minutes
NOTES_LIMIT = 10000


def capture_settings(org):
    return {"auto_assign": False, "form_id": "", **(org.settings.get("lead_capture") or {})}


def save_settings(org, **values):
    org.settings = {**org.settings, "lead_capture": {**capture_settings(org), **values}}


def channel_record(db, org_id, channel, create=False):
    record = db.scalar(rows(db, Integration, org_id).where(Integration.provider == channel))
    if not record and create:
        record = Integration(org_id=org_id, provider=channel, secret=encrypt(""), enabled=False)
        db.add(record)
        db.flush()
    return record


def capture_ready(db, org):
    """Whether any capture channel can currently receive enquiries."""
    form = channel_record(db, org.id, "website-form")
    if form and form.enabled and capture_settings(org)["form_id"]:
        return True
    return any(
        (record := channel_record(db, org.id, channel)) and record.enabled and stored_key(record)
        for channel in KEY_CHANNELS
    )


def stored_key(record):
    try:
        return decrypt(record.secret) if record else ""
    except Exception:
        return ""


def endpoint(org_id, channel):
    return f"{settings.public_origin}/api/capture/{org_id}/{channel}"


def config_dump(db, org):
    values = capture_settings(org)
    form = channel_record(db, org.id, "website-form")
    records = {c: channel_record(db, org.id, c) for c in KEY_CHANNELS}
    integration_ids = [r.id for r in [form, *records.values()] if r]
    names = {r.id: r.provider for r in [form, *records.values()] if r}
    runs = (
        db.scalars(
            rows(db, SyncRun, org.id)
            .where(SyncRun.integration_id.in_(integration_ids))
            .order_by(SyncRun.created_at.desc())
            .limit(20)
        )
        if integration_ids
        else []
    )
    week = now() - timedelta(days=7)
    captured = dict(
        db.execute(
            select(Lead.source, func.count())
            .where(Lead.org_id == org.id, Lead.deleted.is_(False), Lead.enquiry_at >= week)
            .group_by(Lead.source)
        ).all()
    )
    return {
        "auto_assign": bool(values["auto_assign"]),
        "telecallers": db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.org_id == org.id, User.role == "telecaller", User.active.is_(True), User.deleted.is_(False))
        ),
        "form": {
            "enabled": bool(form and form.enabled and values["form_id"]),
            "url": f"{settings.public_origin}/enquiry/{values['form_id']}" if values["form_id"] else "",
            "last_received": form.last_sync.isoformat() if form and form.last_sync else None,
        },
        "channels": [
            {
                "channel": channel,
                "label": CHANNELS[channel][1],
                "configured": bool(stored_key(record)),
                "enabled": bool(record and record.enabled and stored_key(record)),
                "endpoint": endpoint(org.id, channel),
                "last_received": record.last_sync.isoformat() if record and record.last_sync else None,
            }
            for channel, record in records.items()
        ],
        "recent": [
            {
                "id": run.id,
                "channel": names.get(run.integration_id, ""),
                "state": run.state,
                "imported": run.imported,
                "duplicates": run.duplicates,
                "invalid": run.invalid,
                "error": run.error,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ],
        "captured_7d": {source: count for source, count in captured.items() if source},
    }


def text(value, limit):
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()[:limit]


def note_text(label, fields, when):
    stamp = when.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %H:%M IST")
    lines = [f"Enquiry via {label} · {stamp}"]
    lines += [f"{key}: {value}" for key, value in fields if value]
    return "\n".join(lines)


def auto_assign(db, org, lead):
    """Round-robin a captured, unassigned lead to the next active telecaller when enabled."""
    if lead.owner_id or not capture_settings(org)["auto_assign"]:
        return
    callers = list(
        db.scalars(
            select(User)
            .where(User.org_id == org.id, User.role == "telecaller", User.active.is_(True), User.deleted.is_(False))
            .order_by(User.created_at, User.id)
        )
    )
    if not callers:
        return
    target = callers[org.cursor % len(callers)]
    org.cursor += 1
    lead.owner_id = target.id
    db.add(Assignment(org_id=org.id, lead_id=lead.id, previous_id=None, owner_id=target.id, source="auto_capture"))
    db.add(
        Audit(
            org_id=org.id,
            entity="lead",
            entity_id=lead.id,
            action="assigned",
            summary="Lead assigned automatically on capture",
            details={"previous_id": None, "owner_id": target.id, "source": "auto_capture"},
        )
    )
    event(db, org.id, "lead_assigned", lead.id, None)


def capture(db, org, channel, entries):
    """Store normalised enquiries. Each entry: external, name, phone, city, fields (label/value pairs)."""
    source, label = CHANNELS[channel]
    result = {"imported": 0, "merged": 0, "duplicates": 0, "invalid": 0, "lead_ids": []}
    stamp = now()
    for entry in entries:
        try:
            name = text(entry.get("name"), 160)
            normalized = phone(entry.get("phone") or "")
            if len(name) < 2:
                raise ValueError()
        except (HTTPException, ValueError):
            result["invalid"] += 1
            continue
        external = text(entry.get("external"), 500) or uid()
        if len(external) > 120:
            external = "sha256:" + hashlib.sha256(external.encode()).hexdigest()
        if db.scalar(
            rows(db, Provenance, org.id).where(Provenance.provider == channel, Provenance.external_id == external)
        ):
            result["duplicates"] += 1
            continue
        note = note_text(label, entry.get("fields", []), stamp)
        lead = db.scalar(rows(db, Lead, org.id).where(Lead.phone == normalized, Lead.deleted.is_(False)))
        if lead:
            # A repeat enquiry keeps one client record and raises a fresh speed-to-lead alert.
            if len(lead.notes) + len(note) + 2 <= NOTES_LIMIT:
                lead.notes = (lead.notes + "\n\n" + note).strip()
            lead.enquiry_at = stamp
            db.add(
                Audit(
                    org_id=org.id,
                    entity="lead",
                    entity_id=lead.id,
                    action="enquiry_received",
                    summary=f"Repeat enquiry received via {label}",
                    details={"channel": channel},
                )
            )
            result["merged"] += 1
        else:
            lead = Lead(
                org_id=org.id,
                name=name,
                phone=normalized,
                source=source,
                city=text(entry.get("city"), 100),
                notes=note[:NOTES_LIMIT],
                enquiry_at=stamp,
            )
            db.add(lead)
            db.flush()
            db.add(
                Audit(
                    org_id=org.id,
                    entity="lead",
                    entity_id=lead.id,
                    action="created",
                    summary=f"Lead captured via {label}",
                    details={"channel": channel},
                )
            )
            event(db, org.id, "lead_created", lead.id, None)
            result["imported"] += 1
        auto_assign(db, org, lead)
        db.add(Provenance(org_id=org.id, provider=channel, external_id=external, lead_id=lead.id))
        db.flush()
        result["lead_ids"].append(lead.id)
    return result


def record_run(db, record, result, state="success"):
    record.last_sync = now()
    db.add(
        SyncRun(
            org_id=record.org_id,
            integration_id=record.id,
            state=state,
            imported=result["imported"] + result["merged"],
            duplicates=result["duplicates"],
            invalid=result["invalid"],
        )
    )


def active_org(db, org_id):
    org = lock_org(db, org_id)
    if not org or not org.active or org.deleted:
        fail("not_found", "Lead capture is not available", 404)
    return org


def verified_record(db, org_id, channel, supplied):
    record = channel_record(db, org_id, channel)
    key = stored_key(record)
    if not (record and record.enabled and key and supplied) or not hmac.compare_digest(
        str(supplied).encode("utf-8"), key.encode("utf-8")
    ):
        fail("invalid_webhook_token", "Lead capture authentication failed", 401)
    return record


# ---------- Company administrator settings ----------


class LeadCaptureIn(Payload):
    form_enabled: bool | None = None
    auto_assign: bool | None = None


@router.get("/lead-capture")
def get_settings(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin")
    return config_dump(db, ctx.org)


@router.put("/lead-capture")
def put_settings(data: LeadCaptureIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    org = ctx.org
    if data.auto_assign is not None:
        save_settings(org, auto_assign=data.auto_assign)
    if data.form_enabled is not None:
        form = channel_record(db, org.id, "website-form", create=True)
        form.enabled = data.form_enabled
        if data.form_enabled and not capture_settings(org)["form_id"]:
            save_settings(org, form_id=secrets.token_urlsafe(18))
    audit(db, ctx, "integration", org.id, "lead_capture_updated", "Lead capture settings updated", data.model_dump())
    db.flush()
    return config_dump(db, org)


@router.post("/lead-capture/form/new-link")
def new_form_link(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    save_settings(ctx.org, form_id=secrets.token_urlsafe(18))
    audit(db, ctx, "integration", ctx.org_id, "form_link_replaced", "Enquiry form link replaced; old link stopped")
    db.flush()
    return config_dump(db, ctx.org)


@router.post("/lead-capture/{channel}/key")
def generate_key(channel: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    if channel not in KEY_CHANNELS:
        fail("unsupported_channel", "Choose the website integration or Google Ads", 422)
    key = secrets.token_urlsafe(32)
    record = channel_record(db, ctx.org_id, channel, create=True)
    record.secret, record.enabled, record.last_error = encrypt(key), True, ""
    audit(db, ctx, "integration", record.id, "key_generated", f"Generated a new {channel} capture key; key redacted")
    db.flush()
    # The key is returned once. Afterwards only whether it is configured is shown.
    return {"key": key, **config_dump(db, ctx.org)}


@router.delete("/lead-capture/{channel}/key")
def revoke_key(channel: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    record = channel_record(db, ctx.org_id, channel)
    if channel not in KEY_CHANNELS or not record:
        fail("not_found", "This capture channel is not set up", 404)
    record.secret, record.enabled = encrypt(""), False
    audit(db, ctx, "integration", record.id, "key_revoked", f"Turned off {channel} capture and revoked its key")
    db.flush()
    return config_dump(db, ctx.org)


# ---------- Server-to-server intake ----------

NAME_KEYS = ("name", "full_name", "fullname", "customer_name")
PHONE_KEYS = ("phone", "mobile", "phone_number", "mobile_number", "contact")
KNOWN = {
    "email": "Email",
    "purpose": "Looking to",
    "budget": "Budget",
    "project": "Project",
    "property": "Property",
    "location": "Preferred location",
    "message": "Message",
    "enquiry": "Message",
    "comments": "Message",
}


def website_entry(item):
    if not isinstance(item, dict):
        return {}
    lowered = {str(k).strip().lower(): v for k, v in item.items()}
    name = next((text(lowered[k], 160) for k in NAME_KEYS if text(lowered.get(k), 160)), "")
    if not name:
        name = " ".join(filter(None, [text(lowered.get("first_name"), 80), text(lowered.get("last_name"), 80)]))
    used = {*NAME_KEYS, *PHONE_KEYS, "first_name", "last_name", "city", "id", "external_id", "lead_id", *KNOWN}
    fields = [(label, text(lowered.get(key), 2000)) for key, label in KNOWN.items()]
    extra = [(str(k)[:60], text(v, 500)) for k, v in item.items() if str(k).strip().lower() not in used]
    return {
        "external": text(lowered.get("external_id") or lowered.get("id") or lowered.get("lead_id"), 500),
        "name": name,
        "phone": next((lowered[k] for k in PHONE_KEYS if text(lowered.get(k), 40)), ""),
        "city": lowered.get("city"),
        "fields": fields + extra[:15],
    }


async def json_body(request, limit=100):
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        fail("payload_too_large", "Send at most 1 MiB", 413)
    try:
        data = await request.json()
    except Exception:
        fail("invalid_payload", "Send JSON", 422)
    items = data if isinstance(data, list) else [data]
    if len(items) > limit or any(not isinstance(item, dict) for item in items):
        fail("invalid_payload", f"Send one JSON enquiry or a list of at most {limit}", 422)
    return items


@router.post("/capture/{org_id}/website")
async def website_webhook(
    org_id: str,
    request: Request,
    x_webhook_token: str = Header(default=""),
    db: Session = Depends(get_db, scope="function"),
):
    org = active_org(db, org_id)
    record = verified_record(db, org_id, "website", x_webhook_token)
    items = await json_body(request)
    result = capture(db, org, "website", [website_entry(item) for item in items])
    record_run(db, record, result)
    return {k: v for k, v in result.items() if k != "lead_ids"}


GOOGLE_FIELDS = {
    "FULL_NAME": "name",
    "PHONE_NUMBER": "phone",
    "CITY": "city",
}


@router.post("/capture/{org_id}/google-ads")
async def google_ads_webhook(org_id: str, request: Request, db: Session = Depends(get_db, scope="function")):
    """Google Ads lead form webhook. Google sends the configured key in the body as google_key."""
    org = active_org(db, org_id)
    [item] = await json_body(request, limit=1)
    record = verified_record(db, org_id, "google-ads", item.get("google_key"))
    columns = item.get("user_column_data") if isinstance(item.get("user_column_data"), list) else []
    values, fields = {}, []
    for column in columns[:50]:
        if not isinstance(column, dict):
            continue
        column_id = text(column.get("column_id"), 60).upper()
        value = text(column.get("string_value"), 2000)
        if column_id in GOOGLE_FIELDS:
            values[GOOGLE_FIELDS[column_id]] = value
        elif column_id in ("FIRST_NAME", "LAST_NAME"):
            values[column_id] = value
        elif value:
            label = text(column.get("column_name"), 60) or column_id.replace("_", " ").capitalize()
            fields.append((label, value))
    name = values.get("name") or " ".join(filter(None, [values.get("FIRST_NAME"), values.get("LAST_NAME")]))
    fields += [("Campaign ID", text(item.get("campaign_id"), 60)), ("Form ID", text(item.get("form_id"), 60))]
    if item.get("is_test") is True:
        # Google's "Send test data" proves the connection without creating a client record.
        record_run(db, record, {"imported": 0, "merged": 0, "duplicates": 0, "invalid": 0}, state="test")
        return {}
    entry = {
        "external": text(item.get("lead_id"), 500),
        "name": name,
        "phone": values.get("phone", ""),
        "city": values.get("city"),
        "fields": fields,
    }
    result = capture(db, org, "google-ads", [entry])
    record_run(db, record, result)
    if result["invalid"]:
        record.last_error = "A Google Ads lead was missing a valid name or phone number"
    return {}


# ---------- Hosted enquiry form (public, same-origin) ----------


def form_org(db, form_id, lock=False):
    if not form_id or len(form_id) > 64:
        fail("not_found", "This enquiry form is not available", 404)
    org_id = db.scalar(
        select(Organization.id).where(
            Organization.settings["lead_capture"]["form_id"].as_string() == form_id,
            Organization.active.is_(True),
            Organization.deleted.is_(False),
        )
    )
    org = (lock_org(db, org_id) if lock else db.get(Organization, org_id)) if org_id else None
    form = channel_record(db, org.id, "website-form") if org else None
    if not org or not form or not form.enabled or capture_settings(org)["form_id"] != form_id:
        fail("not_found", "This enquiry form is not available", 404)
    return org, form


@router.get("/public/enquiry/{form_id}")
def form_details(form_id: str, db: Session = Depends(get_db, scope="function")):
    org, _ = form_org(db, form_id)
    return {
        "company": org.settings.get("brand_name") or org.name,
        "real_estate": org.settings.get("industry") == "real_estate",
    }


class EnquiryIn(Payload):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=6, max_length=30)
    email: str = Field(default="", max_length=160, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    city: str = Field(default="", max_length=100)
    purpose: Literal["", "buy", "rent", "sell", "invest"] = ""
    budget: str = Field(default="", max_length=60)
    message: str = Field(default="", max_length=2000)
    consent: bool
    # Hidden from people; automated form fillers that complete it are ignored.
    website: str = Field(default="", max_length=200)


@router.post("/public/enquiry/{form_id}")
def submit_enquiry(form_id: str, data: EnquiryIn, request: Request, db: Session = Depends(get_db, scope="function")):
    require_browser_request(request)
    org, form = form_org(db, form_id, lock=True)
    company = org.settings.get("brand_name") or org.name
    if not data.consent:
        fail("consent_required", f"Agree to be contacted by {company} to send your enquiry", 422)
    if data.website:
        return {"ok": True, "company": company}
    normalized = phone(data.phone)
    recent = now() - timedelta(minutes=10)
    submitted = list(
        db.scalars(
            rows(db, Provenance, org.id)
            .where(Provenance.provider == "website-form", Provenance.created_at >= recent)
            .with_only_columns(Provenance.lead_id)
        )
    )
    if len(submitted) >= FORM_RATE_LIMIT:
        fail("rate_limited", "Too many enquiries were sent just now. Please try again in a few minutes", 429)
    lead = db.scalar(rows(db, Lead, org.id).where(Lead.phone == normalized, Lead.deleted.is_(False)))
    if lead and lead.id in submitted and lead.enquiry_at and lead.enquiry_at >= now() - timedelta(minutes=2):
        # A double-click or immediate resend is acknowledged without a second note.
        return {"ok": True, "company": company}
    entry = {
        "name": data.name,
        "phone": normalized,
        "city": data.city,
        "fields": [
            ("Email", data.email),
            ("Looking to", data.purpose),
            ("Budget", data.budget),
            ("Message", data.message),
            ("Consent", "Agreed to be contacted"),
        ],
    }
    result = capture(db, org, "website-form", [entry])
    record_run(db, form, result)
    return {"ok": True, "company": company}
