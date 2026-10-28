import hashlib
import hmac
from datetime import timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from .common import audit, dump, event, mutate, rows
from .db import get_db, now, uid
from .models import Integration, Job, Lead, Provenance, SyncRun
from .schemas import IntegrationIn
from .security import current, decrypt, encrypt, fail, lock_org, phone, roles, workspace

router = APIRouter(prefix="/api", tags=["Lead provider integrations"])


def credential(record):
    try:
        return decrypt(record.secret)
    except Exception:
        return ""


def integration_dump(record):
    configured = bool(credential(record))
    return {
        **dump(record),
        "configured": configured,
        "credential": "••••••••" if configured else "",
        "state": "setup_required"
        if not configured
        else "paused"
        if not record.enabled
        else "error"
        if record.last_error
        else "configured",
        "verification": "Provider credentials and a real delivery are required to verify connection",
    }


@router.get("/integrations")
def list_integrations(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin", "manager")
    records = {r.provider: r for r in db.scalars(rows(db, Integration, ctx.org_id))}
    return {
        "items": [
            integration_dump(records[p])
            if p in records
            else {"provider": p, "state": "setup_required", "configured": False}
            for p in ["indiamart", "justdial"]
        ],
        "runs": [
            dump(r) for r in db.scalars(rows(db, SyncRun, ctx.org_id).order_by(SyncRun.created_at.desc()).limit(50))
        ],
    }


@router.put("/integrations/{provider}")
def configure(
    provider: str, data: IntegrationIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin")
    mutate(db, ctx)
    if provider not in ["indiamart", "justdial"]:
        fail("unsupported_provider", "Only IndiaMART polling and Justdial webhooks are implemented", 422)
    record = db.scalar(rows(db, Integration, ctx.org_id).where(Integration.provider == provider))
    if not record:
        if not data.credential:
            fail("credential_required", "Enter a CRM key or webhook token", 422)
        record = Integration(org_id=ctx.org_id, provider=provider, secret=encrypt(data.credential))
        db.add(record)
    elif data.credential:
        record.secret = encrypt(data.credential)
    elif data.enabled and not credential(record):
        fail("credential_required", "Enter a new credential to reconnect", 422)
    record.enabled, record.last_error = data.enabled, ""
    db.flush()
    audit(db, ctx, "integration", record.id, "configured", f"Configured {provider}; credentials redacted")
    return integration_dump(record)


@router.delete("/integrations/{provider}")
def disconnect(provider: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    record = db.scalar(rows(db, Integration, ctx.org_id).where(Integration.provider == provider))
    if not record:
        fail("not_found", "Integration not found", 404)
    record.enabled = False
    record.secret = encrypt("")
    record.last_error = "Disconnected. Configure a new credential to reconnect."
    return {"ok": True}


@router.post("/integrations/{provider}/sync")
def manual_sync(provider: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    record = db.scalar(rows(db, Integration, ctx.org_id).where(Integration.provider == provider))
    if not record or not record.enabled or not credential(record):
        fail("setup_required", "Configure and enable this integration first", 409)
    if provider != "indiamart":
        fail("push_provider", "Justdial delivers to the webhook; there is no manual pull", 422)
    pending = db.scalar(rows(db, Job, ctx.org_id).where(Job.kind == "provider", Job.state == "pending"))
    if pending:
        return {"job_id": pending.id, "state": "pending"}
    job = Job(org_id=ctx.org_id, kind="provider", key=uid(), payload={"integration_id": record.id})
    db.add(job)
    db.flush()
    return {"job_id": job.id, "state": "pending"}


def ingest(db, integration, records):
    result = {"imported": 0, "duplicates": 0, "invalid": 0}
    if len(records) > 10000:
        raise ValueError(
            "Provider returned more than 10,000 records; cursor retained. Contact support to recover the batch"
        )
    for item in records:
        try:
            external = str(
                item.get("UNIQUE_QUERY_ID") or item.get("QUERY_ID") or item.get("leadid") or item.get("id") or ""
            )
            if len(external) > 120:
                external = "sha256:" + hashlib.sha256(external.encode()).hexdigest()
            name = str(item.get("SENDER_NAME") or item.get("name") or item.get("customer_name") or "").strip()[:160]
            normalized = phone(item.get("SENDER_MOBILE") or item.get("mobile") or item.get("phone") or "")
            if len(name) < 2:
                raise ValueError()
            if not external:
                external = hashlib.sha256((name + normalized + str(item.get("date", ""))).encode()).hexdigest()
        except Exception:
            result["invalid"] += 1
            continue
        previous = db.scalar(
            rows(db, Provenance, integration.org_id).where(
                Provenance.provider == integration.provider, Provenance.external_id == external
            )
        )
        existing = db.scalar(
            rows(db, Lead, integration.org_id).where(Lead.phone == normalized, Lead.deleted.is_(False))
        )
        if previous:
            result["duplicates"] += 1
            continue
        if existing:
            result["duplicates"] += 1
            lead = existing
        else:
            lead = Lead(
                org_id=integration.org_id,
                name=name,
                phone=normalized,
                source=integration.provider,
                city=str(item.get("SENDER_CITY") or item.get("city") or "")[:100],
                state=str(item.get("SENDER_STATE") or item.get("state") or "")[:100],
                notes=str(item.get("QUERY_MESSAGE") or item.get("enquiry") or item.get("message") or "")[:10000],
            )
            db.add(lead)
            db.flush()
            result["imported"] += 1
            event(db, integration.org_id, "lead_created", lead.id, None)
        db.add(
            Provenance(org_id=integration.org_id, provider=integration.provider, external_id=external, lead_id=lead.id)
        )
        db.flush()
    return result


def poll_indiamart(db, integration):
    secret = decrypt(integration.secret)
    if not secret:
        raise ValueError("Integration credentials are missing")
    current_time = now()
    start = integration.last_sync - timedelta(minutes=5) if integration.last_sync else current_time - timedelta(days=1)
    end = min(current_time, start + timedelta(days=7))
    zone = ZoneInfo("Asia/Kolkata")
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.get(
            "https://mapi.indiamart.com/wservice/crm/crmListing/v2/",
            params={
                "glusr_crm_key": secret,
                "start_time": start.astimezone(zone).strftime("%d-%m-%Y %H:%M:%S"),
                "end_time": end.astimezone(zone).strftime("%d-%m-%Y %H:%M:%S"),
            },
        )
        if response.status_code == 429:
            raise ValueError("Provider rate limited the request; retry will be delayed")
        if response.status_code != 200:
            raise ValueError(f"Provider returned HTTP {response.status_code}")
        if len(response.content) > 10 * 1024 * 1024:
            raise ValueError("Provider response exceeds 10 MiB")
        data = response.json()
        if not isinstance(data, dict) or str(data.get("CODE")) not in ["200", "204"]:
            raise ValueError("Provider rejected the request. Verify the CRM key and account access")
        records = data.get("RESPONSE", [])
        if not isinstance(records, list):
            raise ValueError("Provider response has an unsupported record format")
    result = ingest(db, integration, records)
    integration.last_sync, integration.last_error = end, ""
    db.add(SyncRun(org_id=integration.org_id, integration_id=integration.id, state="success", **result))
    return result


@router.post("/webhooks/justdial/{org_id}")
async def justdial(
    org_id: str,
    request: Request,
    x_webhook_token: str = Header(default=""),
    db: Session = Depends(get_db, scope="function"),
):
    org = lock_org(db, org_id)
    if not org or not org.active or org.deleted:
        fail("not_found", "Integration not found", 404)
    integration = db.scalar(rows(db, Integration, org_id).where(Integration.provider == "justdial"))
    if (
        not integration
        or not integration.enabled
        or not x_webhook_token
        or not hmac.compare_digest(x_webhook_token.encode("utf-8"), credential(integration).encode("utf-8"))
    ):
        fail("invalid_webhook_token", "Webhook authentication failed", 401)
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        fail("payload_too_large", "Webhook exceeds 1 MiB", 413)
    try:
        data = await request.json()
        records = data if isinstance(data, list) else [data]
        if len(records) > 100 or any(not isinstance(item, dict) for item in records):
            raise ValueError()
    except Exception:
        fail("invalid_payload", "Send one JSON lead or a list of at most 100 leads", 422)
    result = ingest(db, integration, records)
    integration.last_sync = now()
    db.add(SyncRun(org_id=org_id, integration_id=integration.id, state="success", **result))
    return result
