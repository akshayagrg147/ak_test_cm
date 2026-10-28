import io
import wave
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import SessionLocal, now
from app.integrations import poll_indiamart
from app.models import AuthSession, Integration, Job
from app.security import decrypt
from app.worker import process_organization
from conftest import PASSWORD, make_lead


def audio_bytes():
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0" * 1600)
    return data.getvalue()


def test_justdial_authenticated_idempotent_isolated_delivery(env):
    c, ids = env
    secret = "private-provider-test-token-123"
    body = {"credential": secret, "enabled": True}
    assert c["manager"].put("/api/integrations/justdial", json=body).status_code == 403
    assert c["admin"].put("/api/integrations/justdial", json=body).status_code == 200
    public = c["manager"].get("/api/integrations").json()
    assert secret not in str(public) and public["items"][1]["configured"]
    path = "/api/webhooks/justdial/" + ids["org"]
    lead = {
        "leadid": "provider-id-1",
        "name": "Justdial Customer",
        "mobile": "9810001234",
        "city": "Pune",
        "enquiry": "Needs a proposal",
    }
    assert c["other"].post(path, json=lead).status_code == 401
    headers = {"X-Webhook-Token": secret}
    r = c["other"].post(path, json=lead, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    assert c["other"].post(path, json=lead, headers=headers).json()["duplicates"] == 1
    leads = c["admin"].get("/api/leads").json()["items"]
    assert len(leads) == 1 and leads[0]["source"] == "justdial" and leads[0]["owner_id"] is None
    assert c["other"].get("/api/leads").json()["total"] == 0
    assert c["other"].post(path, json=[{"name": "Bad", "mobile": "bad"}], headers=headers).json()["invalid"] == 1
    assert c["other"].post(path, json="wrong shape", headers=headers).status_code == 422
    assert c["other"].post(path, json=[lead] * 101, headers=headers).status_code == 422
    assert c["admin"].put("/api/integrations/justdial", json={"enabled": False}).status_code == 200
    assert c["other"].post(path, json=lead, headers=headers).status_code == 401
    c["admin"].delete("/api/integrations/justdial")
    assert c["admin"].get("/api/integrations").json()["items"][1]["state"] == "setup_required"
    assert c["admin"].put("/api/integrations/justdial", json={"enabled": True}).status_code == 422


class FakeProvider:
    response = None
    error = None
    requests = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, params):
        self.requests.append({"url": url, "params": params})
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize(
    "status,payload,error",
    [
        (
            200,
            {
                "CODE": 200,
                "RESPONSE": [
                    {
                        "UNIQUE_QUERY_ID": "im-id-1",
                        "SENDER_NAME": "IndiaMART Customer",
                        "SENDER_MOBILE": "9810001234",
                        "SENDER_CITY": "Pune",
                        "QUERY_MESSAGE": "Need supplies",
                    }
                ],
            },
            None,
        ),
        (429, {}, "rate limited"),
        (503, {}, "HTTP 503"),
        (200, {"CODE": 401}, "rejected"),
        (200, {"CODE": 200, "RESPONSE": {}}, "unsupported"),
    ],
)
def test_indiamart_success_failures_and_secret_encryption(env, monkeypatch, status, payload, error):
    c, ids = env
    secret = "indiamart-test-secret-12345"
    assert c["admin"].put("/api/integrations/indiamart", json={"credential": secret}).status_code == 200
    FakeProvider.response = httpx.Response(status, json=payload)
    FakeProvider.error = None
    FakeProvider.requests = []
    monkeypatch.setattr("app.integrations.httpx.Client", FakeProvider)
    with SessionLocal.begin() as db:
        integration = db.scalar(select(Integration).where(Integration.org_id == ids["org"]))
        assert secret not in integration.secret and decrypt(integration.secret) == secret
        if error:
            with pytest.raises(ValueError, match=error):
                poll_indiamart(db, integration)
        else:
            result = poll_indiamart(db, integration)
            assert result["imported"] == 1
            result = poll_indiamart(db, integration)
            assert result["duplicates"] == 1
    assert FakeProvider.requests[0]["url"] == "https://mapi.indiamart.com/wservice/crm/crmListing/v2/"
    if not error:
        assert c["admin"].get("/api/leads").json()["items"][0]["owner_id"] is None


def test_provider_retry_does_not_block_other_organization(env, monkeypatch):
    c, ids = env
    c["admin"].put("/api/integrations/indiamart", json={"credential": "indiamart-test-secret-12345"})
    FakeProvider.error = httpx.ReadTimeout("timeout")
    FakeProvider.requests = []
    monkeypatch.setattr("app.integrations.httpx.Client", FakeProvider)
    first = c["admin"].post("/api/integrations/indiamart/sync")
    assert first.status_code == 200
    assert c["admin"].post("/api/integrations/indiamart/sync").json()["job_id"] == first.json()["job_id"]
    process_organization(ids["org"])
    assert c["admin"].get("/api/integrations").json()["items"][0]["state"] == "error"
    make_lead(c["other"], name="Other org remains usable")
    assert c["other"].get("/api/analytics").json()["metrics"]["leads"] == 1
    assert "secret" not in str(c["manager"].get("/api/integrations").json()["runs"])
    with SessionLocal() as db:
        job = db.get(Job, first.json()["job_id"])
        assert job.state == "pending" and job.available_at > now()


def test_file_content_size_traversal_current_authorization_and_duplicate_audio(env):
    c, ids = env
    lead = make_lead(c["caller"])
    path = "/api/leads/" + lead["id"] + "/files"
    assert c["caller"].post(path, files={"file": ("fake.mp3", b"<html>bad</html>", "audio/mpeg")}).status_code == 422
    assert c["caller"].post(path, files={"file": ("empty.pdf", b"", "application/pdf")}).status_code == 422
    assert (
        c["caller"]
        .post(path, files={"file": ("huge.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), "application/pdf")})
        .status_code
        == 413
    )
    from pypdf import PdfWriter

    document = PdfWriter()
    document.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    document.write(output)
    raw = output.getvalue()
    r = c["caller"].post(path, files={"file": ("../../../../secret.pdf", raw, "application/pdf")})
    assert r.status_code == 201, r.text
    record = r.json()
    assert record["name"] == "secret.pdf" and "storage_key" not in record
    assert c["caller"].post(path, files={"file": ("same.pdf", raw, "application/pdf")}).json()["id"] == record["id"]
    assert c["caller2"].get("/api/files/" + record["id"]).status_code == 404
    d = c["admin"].get("/api/files/" + record["id"])
    assert d.content == raw and d.headers["cache-control"] == "no-store"
    assert c["manager"].delete("/api/files/" + record["id"]).status_code == 403
    assert c["caller"].delete("/api/files/" + record["id"]).status_code == 200
    assert c["admin"].get("/api/files/" + record["id"]).status_code == 404
    calls = [
        {
            "device_call_id": str(i),
            "phone": lead["phone"],
            "direction": "outgoing",
            "result": "answered",
            "started_at": (now() - timedelta(minutes=i)).isoformat(),
            "duration": 60,
        }
        for i in range(2)
    ]
    c["caller"].post("/api/phone-calls/sync", json={"device_id": "recording-device", "calls": calls})
    pcs = c["caller"].get("/api/phone-calls").json()["items"]
    raw = audio_bytes()
    r = c["caller"].post(
        path, data={"phone_call_id": pcs[0]["id"]}, files={"file": ("recording.wav", raw, "audio/wav")}
    )
    assert r.status_code == 201
    assert (
        c["caller"]
        .post(path, data={"phone_call_id": pcs[0]["id"]}, files={"file": ("recording.wav", raw, "audio/wav")})
        .json()["id"]
        == r.json()["id"]
    )
    assert (
        c["caller"]
        .post(path, data={"phone_call_id": pcs[1]["id"]}, files={"file": ("recording.wav", raw, "audio/wav")})
        .status_code
        == 409
    )
    assert (
        c["caller"]
        .post(
            path, data={"phone_call_id": pcs[1]["id"]}, files={"file": ("document.pdf", b"%PDF-1.4", "application/pdf")}
        )
        .status_code
        == 422
    )


@pytest.mark.parametrize("linked", [False, True], ids=["audio-file", "call-recording"])
@pytest.mark.parametrize("uploader", ["caller", "admin"])
def test_telecaller_cannot_delete_any_recording_even_own_upload(env, linked, uploader):
    c, _ = env
    lead = make_lead(c["caller"])
    data = {}
    if linked:
        synced = c["caller"].post("/api/phone-calls/sync", json={
            "device_id": "protected-recordings",
            "calls": [{"device_call_id": "own-call", "phone": lead["phone"], "direction": "outgoing",
                       "result": "answered", "started_at": now().isoformat(), "duration": 30}],
        })
        assert synced.status_code == 200, synced.text
        data["phone_call_id"] = synced.json()["entries"][0]["call_id"]
    raw = audio_bytes()
    # File suffix/client MIME must not let an audio upload evade the policy.
    response = c[uploader].post(f"/api/leads/{lead['id']}/files", data=data,
                              files={"file": ("recording.pdf", raw, "application/pdf")})
    assert response.status_code == 201, response.text
    attachment = response.json()
    assert attachment["mime"] == "audio/wav"
    path = "/api/files/" + attachment["id"]
    for _ in range(2):
        denied = c["caller"].delete(path)
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "recording_delete_forbidden"
        assert c["caller"].get(path + "?inline=true").content == raw
    assert c["other"].delete(path).status_code == 404
    assert c["caller2"].delete(path).status_code == 404
    if linked:
        call = c["caller"].get("/api/phone-calls").json()["items"][0]
        assert call["recording_state"] == "attached"
        assert [f["id"] for f in call["recordings"]] == [attachment["id"]]
    assert c["admin"].delete(path).status_code == 200
    assert c["admin"].get(path).status_code == 404
    if linked:
        assert c["caller"].get("/api/phone-calls").json()["items"][0]["recording_state"] == "unavailable"


def test_administrator_logged_in_as_telecaller_cannot_delete_member_recording(env):
    c, ids = env
    lead = make_lead(c["caller"])
    raw = audio_bytes()
    response = c["caller"].post(f"/api/leads/{lead['id']}/files", files={"file": ("own.wav", raw)})
    assert response.status_code == 201
    path = "/api/files/" + response.json()["id"]
    member = c["admin"].post(f"/api/team/{ids['caller']}/login-as")
    assert member.status_code == 200
    headers = {"Authorization": "Bearer " + member.json()["access_token"]}
    assert c["admin"].delete(path, headers=headers).status_code == 403
    assert c["admin"].get(path, headers=headers).content == raw
    restored = c["admin"].post("/api/auth/login-as/exit")
    assert restored.status_code == 200
    assert c["admin"].delete(path, headers={"Authorization": "Bearer " + restored.json()["access_token"]}).status_code == 200


def test_platform_create_two_organizations_member_guards_and_delete(env):
    c, _ = env
    ids = []
    for i in range(2):
        r = c["owner"].post(
            "/api/platform/organizations",
            json={
                "name": f"Isolated Business {i}",
                "admin": {"name": "First Admin", "phone": f"99000010{90 + i}", "password": PASSWORD, "role": "admin"},
            },
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["organization"]["id"])
    assert c["owner"].get("/api/platform").json()["total"] == 4
    for org_id in ids:
        assert len(c["owner"].get("/api/platform/organizations/" + org_id).json()["members"]) == 1
    assert c["owner"].delete("/api/platform/organizations/" + ids[0] + "?confirmation=wrong").status_code == 422
    assert (
        c["owner"].delete("/api/platform/organizations/" + ids[0] + "?confirmation=Isolated%20Business%200").status_code
        == 200
    )
    assert c["owner"].get("/api/platform/organizations/" + ids[0]).status_code == 404
    assert c["owner"].get("/api/platform").json()["total"] == 3


def test_expired_support_can_always_exit_with_valid_refresh_cookie(env):
    c, ids = env
    r = c["owner"].post("/api/platform/organizations/" + ids["org"] + "/support")
    assert r.status_code == 200
    c["owner"].headers["Authorization"] = "Bearer " + r.json()["access_token"]
    with SessionLocal.begin() as db:
        for s in db.scalars(select(AuthSession).where(AuthSession.support_org == ids["org"])):
            s.support_until = now() - timedelta(minutes=1)
    assert c["owner"].get("/api/leads").status_code == 401
    r = c["owner"].post("/api/auth/support/exit")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "owner" and not r.json()["support"]


def test_automation_task_and_assignment_actions_do_not_recurse(env):
    c, ids = env
    for action, config in [
        ("create_task", {"title": "Prepare an introduction", "delay_minutes": 30}),
        ("assign_manager", {"manager_id": ids["manager"]}),
    ]:
        r = c["admin"].post(
            "/api/automations", json={"name": action, "trigger": "lead_created", "action": action, "config": config}
        )
        assert r.status_code == 201
    lead = make_lead(c["caller"])
    process_organization(ids["org"])
    process_organization(ids["org"])
    assert c["admin"].get("/api/leads/" + lead["id"]).json()["owner_id"] == ids["manager"]
    tasks = c["admin"].get("/api/tasks").json()
    assert len(tasks) == 1 and tasks[0]["title"] == "Prepare an introduction"
    assert c["admin"].get("/api/automations").json()["runs"][0]["state"] == "success"


@pytest.mark.parametrize(
    "config",
    [
        {"type": "banana"},
        {"type": "select", "options": []},
        {"type": "select", "options": ["A", "A"]},
        {"type": "text", "required": "yes"},
    ],
)
def test_bad_custom_field_definitions(env, config):
    c, _ = env
    assert (
        c["admin"]
        .post(
            "/api/definitions",
            json={"kind": "field", "key": "custom_field", "label": "A custom field", "config": config},
        )
        .status_code
        == 422
    )
