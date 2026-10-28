from datetime import timedelta
import io
import wave

from sqlalchemy import select

from app.db import SessionLocal, now
from app.models import PhoneCall
from conftest import make_lead


def entry(lead, identity="log-1"):
    return {"device_call_id": identity, "phone": lead["phone"], "direction": "incoming", "result": "answered", "started_at": now().isoformat(), "duration": 30}


def test_device_contacts_scope_keyset_and_revocation(env):
    c, ids = env
    own = [make_lead(c["caller"], name=f"Own {i}", phone=f"+91981006000{i}") for i in range(3)]
    make_lead(c["caller2"], phone="+919810060009")
    collected, cursor = [], ""
    while True:
        response = c["caller"].get("/api/phone-calls/contacts", params={"limit": 1, "after": cursor})
        assert response.status_code == 200
        page = response.json()
        assert page["user_id"] == ids["caller"] and page["organization_id"] == ids["org"]
        assert page["max_recording_bytes"] == 64 * 1024 * 1024
        collected.extend(page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert {row["id"] for row in collected} == {lead["id"] for lead in own}
    assert all(set(row) == {"id", "name", "phone", "dnd"} for row in collected)
    for role in ["admin", "owner", "other"]:
        assert c[role].get("/api/phone-calls/contacts").status_code == 403
    assert c["caller"].get("/api/phone-calls/contacts?limit=201").status_code == 422
    assert c["caller"].get("/api/phone-calls/contacts?limit=0").status_code == 422
    c["admin"].post("/api/leads/assign", json={"lead_ids": [lead["id"] for lead in own], "owner_id": ids["caller2"]})
    assert c["caller"].get("/api/phone-calls/contacts").json()["items"] == []
    assert len(c["caller2"].get("/api/phone-calls/contacts").json()["items"]) == 4


def test_per_call_receipts_support_retry_reassignment_and_upload(env):
    c, ids = env
    lead = make_lead(c["caller"])
    body = {"device_id": "android-installation-001", "calls": [entry(lead), entry(lead, "log-2")]}
    first = c["caller"].post("/api/phone-calls/sync", json=body).json()
    assert first["created"] == 2
    receipts = first["entries"]
    assert {r["device_call_id"] for r in receipts} == {"log-1", "log-2"}
    assert all(r["lead_id"] == lead["id"] and r["status"] == "created" and r["call_id"] for r in receipts)
    second = c["caller"].post("/api/phone-calls/sync", json=body).json()
    assert second["updated"] == 2
    assert [r["call_id"] for r in second["entries"]] == [r["call_id"] for r in receipts]
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x01\x00" * 8000)
    path = f"/api/leads/{lead['id']}/files"
    def upload():
        return c["caller"].post(path, data={"phone_call_id": receipts[0]["call_id"]}, files={"file": ("native-call.wav", audio.getvalue())})

    attachment = upload()
    assert attachment.status_code == 201
    assert upload().json()["id"] == attachment.json()["id"]
    c["admin"].post("/api/leads/assign", json={"lead_ids": [lead["id"]], "owner_id": ids["caller2"]})
    revoked = c["caller"].post("/api/phone-calls/sync", json=body).json()
    assert all(r == {"device_call_id": r["device_call_id"], "status": "excluded"} for r in revoked["entries"])
    assert upload().status_code == 404


def test_each_invalid_or_ambiguous_entry_has_a_non_sensitive_receipt(env):
    c, _ = env
    lead = make_lead(c["caller"])
    calls = [entry(lead), {**entry(lead, "personal"), "phone": "+919810060009"}, {**entry(lead, "bad-number"), "phone": "bad"}, {**entry(lead, "old"), "started_at": (now() - timedelta(days=31)).isoformat()}]
    result = c["caller"].post("/api/phone-calls/sync", json={"device_id": "android-receipts-001", "calls": calls}).json()
    assert [r["status"] for r in result["entries"]] == ["created", "excluded", "error", "error"]
    assert result["entries"][2]["code"] == "invalid_phone"
    assert result["entries"][3]["code"] == "outside_sync_window"
    make_lead(c["caller"], name="Duplicate", allow_duplicate=True)
    ambiguous = c["caller"].post("/api/phone-calls/sync", json={"device_id": "android-receipts-001", "calls": [entry(lead)]}).json()
    assert ambiguous["entries"] == [{"device_call_id": "log-1", "status": "ambiguous"}]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(PhoneCall)))) == 1


def test_duplicate_batch_id_is_rejected_before_any_call_is_saved(env):
    c, _ = env
    lead = make_lead(c["caller"])
    response = c["caller"].post("/api/phone-calls/sync", json={"device_id": "android-duplicate-001", "calls": [entry(lead), entry(lead)]})
    assert response.status_code == 422
    with SessionLocal() as db:
        assert list(db.scalars(select(PhoneCall))) == []


def test_reused_number_does_not_restore_access_to_reassigned_historical_call(env):
    c, ids = env
    original = make_lead(c["caller"])
    old = entry(original)
    body = {"device_id": "android-reused-number", "calls": [old]}
    receipt = c["caller"].post("/api/phone-calls/sync", json=body).json()["entries"][0]
    assigned = c["admin"].post("/api/leads/assign", json={"lead_ids": [original["id"]], "owner_id": ids["caller2"]})
    assert assigned.status_code == 200
    replacement = make_lead(c["caller"], name="Different lead sharing the number", allow_duplicate=True)
    denied = c["caller"].post("/api/phone-calls/sync", json={**body, "calls": [{**old, "duration": 99}]}).json()
    assert denied["entries"] == [{"device_call_id": "log-1", "status": "excluded"}]
    with SessionLocal() as db:
        saved = db.get(PhoneCall, receipt["call_id"])
        assert saved.lead_id == original["id"] and saved.duration == 30
    new = c["caller"].post("/api/phone-calls/sync", json={**body, "calls": [entry(replacement, "new-call")]}).json()["entries"][0]
    assert new["status"] == "created" and new["lead_id"] == replacement["id"]


def test_recording_limit_is_separate_from_generic_file_limit(env, monkeypatch):
    from app.config import settings

    c, _ = env
    lead = make_lead(c["caller"])
    receipt = c["caller"].post("/api/phone-calls/sync", json={"device_id": "android-size-limits", "calls": [entry(lead)]}).json()["entries"][0]
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x01\x00" * (6 * 1024 * 1024))
    path = f"/api/leads/{lead['id']}/files"
    raw = audio.getvalue()
    assert settings.max_upload < len(raw) < settings.max_recording_upload
    assert c["caller"].post(path, files={"file": ("large.wav", raw)}).status_code == 413
    linked = c["caller"].post(path, data={"phone_call_id": receipt["call_id"]}, files={"file": ("large.wav", raw)})
    assert linked.status_code == 201
    monkeypatch.setattr(settings, "max_recording_upload", len(raw) - 1)
    assert c["caller"].post(path, data={"phone_call_id": receipt["call_id"]}, files={"file": ("large.wav", raw)}).status_code == 413
