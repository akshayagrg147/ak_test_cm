import io
from datetime import timedelta

from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal, now
from app.models import Job, Lead, Note
from app.worker import process_organization
from conftest import make_lead


def test_logo_transparency_content_validation_and_access(env):
    clients, _ = env
    raw = io.BytesIO()
    Image.new("RGBA", (2, 2), (20, 100, 70, 0)).save(raw, format="PNG")
    content = raw.getvalue()
    response = clients["admin"].post("/api/settings/logo", files={"file": ("logo.png", content, "image/png")})
    assert response.status_code == 200, response.text
    file_id = response.json()["id"]
    downloaded = clients["caller"].get("/api/files/" + file_id)
    assert downloaded.status_code == 200 and downloaded.content == content
    assert Image.open(io.BytesIO(downloaded.content)).getpixel((0, 0))[3] == 0
    assert clients["other"].get("/api/files/" + file_id).status_code == 404
    assert clients["caller"].delete("/api/settings/logo").status_code == 403
    assert clients["admin"].delete("/api/settings/logo").status_code == 200
    assert clients["caller"].get("/api/files/" + file_id).status_code == 403
    assert (
        clients["admin"]
        .post("/api/settings/logo", files={"file": ("fake.png", b"\x89PNG\r\n\x1a\ninvalid", "image/png")})
        .status_code
        == 422
    )


def test_untagged_valid_audio_and_corrupt_container(env):
    import wave

    clients, _ = env
    lead = make_lead(clients["caller"])
    raw = io.BytesIO()
    with wave.open(raw, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0" * 1600)
    path = f"/api/leads/{lead['id']}/files"
    assert clients["caller"].post(path, files={"file": ("valid.wav", raw.getvalue(), "audio/wav")}).status_code == 201
    assert (
        clients["caller"].post(path, files={"file": ("invalid.wav", b"RIFF0000WAVEbroken", "audio/wav")}).status_code
        == 422
    )
    assert (
        clients["caller"].post(path, files={"file": ("invalid.mp3", b"ID3" + b"\0" * 50, "audio/mpeg")}).status_code
        == 422
    )


def test_request_body_limit_including_streamed_input(env):
    clients, _ = env
    response = clients["caller"].post(
        "/api/leads",
        content=iter([b"x" * (6 * 1024 * 1024), b"x" * (6 * 1024 * 1024)]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "body_too_large"


def test_inactive_custom_values_remain_readable_and_immutable(env):
    clients, _ = env
    field = {"kind": "field", "key": "legacy_field", "label": "Legacy field", "config": {"type": "text"}}
    definition = clients["admin"].post("/api/definitions", json=field).json()
    lead = make_lead(clients["caller"], custom={"legacy_field": "Keep this context"})
    assert (
        clients["admin"].put("/api/definitions/" + definition["id"], json={**field, "active": False}).status_code == 200
    )
    response = clients["caller"].patch("/api/leads/" + lead["id"], json={"city": "Pune"})
    assert response.status_code == 200 and response.json()["custom"]["legacy_field"] == "Keep this context"
    for custom in [{}, {"legacy_field": "Forged change"}]:
        assert clients["caller"].patch("/api/leads/" + lead["id"], json={"custom": custom}).status_code == 422


def test_system_stage_semantics_cannot_be_disabled(env):
    clients, _ = env
    stage = next(
        d for d in clients["admin"].get("/api/definitions").json() if d["kind"] == "stage" and d["key"] == "won"
    )
    base = {key: stage[key] for key in ["kind", "key", "label", "config", "position", "active"]}
    assert clients["admin"].put("/api/definitions/" + stage["id"], json={**base, "active": False}).status_code == 409
    assert (
        clients["admin"]
        .put("/api/definitions/" + stage["id"], json={**base, "config": {"closed": False, "won": False}})
        .status_code
        == 409
    )


def test_scheduled_obsolete_callback_does_not_create_work(env):
    clients, ids = env
    clients["admin"].post(
        "/api/automations",
        json={
            "name": "Due callback note",
            "trigger": "callback_due",
            "action": "add_note",
            "config": {"text": "Should not run"},
        },
    )
    lead = make_lead(clients["caller"])
    old = now() - timedelta(hours=1)
    with SessionLocal.begin() as db:
        db.get(Lead, lead["id"]).follow_up = now() + timedelta(days=1)
        db.add(
            Job(
                org_id=ids["org"],
                key="obsolete-callback",
                kind="automation",
                payload={"lead_id": lead["id"], "trigger": "callback_due", "follow_up": old.isoformat()},
            )
        )
    process_organization(ids["org"])
    with SessionLocal() as db:
        assert db.scalar(select(Note).where(Note.lead_id == lead["id"])) is None
        assert db.scalar(select(Job).where(Job.key == "obsolete-callback")).state == "done"


def test_saved_reports_validate_filters_and_remain_private(env):
    clients, _ = env
    base = {"name": "Monthly report", "kind": "analytics"}
    assert (
        clients["caller"].post("/api/saved-views", json={**base, "filters": {"from_date": "not-a-date"}}).status_code
        == 422
    )
    assert (
        clients["caller"].post("/api/saved-views", json={**base, "filters": {"owner_id": {"forged": True}}}).status_code
        == 422
    )
    response = clients["caller"].post(
        "/api/saved-views", json={**base, "filters": {"from_date": "2026-10-01", "to_date": "2026-11-01"}}
    )
    assert response.status_code == 201
    assert clients["caller2"].get("/api/saved-views").json() == []


def test_support_cannot_create_a_personal_employee_attendance_record(env):
    clients, ids = env
    response = clients["owner"].post(f"/api/platform/organizations/{ids['org']}/support")
    clients["owner"].headers["Authorization"] = "Bearer " + response.json()["access_token"]
    assert (
        clients["owner"]
        .post("/api/attendance/check-in", json={"latitude": 19.076, "longitude": 72.8777, "accuracy": 5})
        .status_code
        == 403
    )
