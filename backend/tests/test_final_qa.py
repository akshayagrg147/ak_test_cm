"""Regression checks from the final requirement and failure-path audit."""

import csv
import io
import threading
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import SessionLocal, now
from app.integrations import ingest, poll_indiamart
from app.models import Attachment, Audit, Integration, Lead, Note, PhoneCall, Provenance, TimeEntry
from app.security import encrypt
from conftest import make_lead


@pytest.mark.parametrize("endpoint", ["/api/leads", "/api/tasks", "/api/phone-calls"])
@pytest.mark.parametrize(
    "filters,code",
    [
        ({"from_date": "2026-10-01T00:00:00"}, "timezone_required"),
        ({"to_date": "2026-10-01T00:00:00"}, "timezone_required"),
        ({"from_date": "2026-10-02T00:00:00Z", "to_date": "2026-10-01T00:00:00Z"}, "invalid_date_range"),
        ({"from_date": "2026-10-01T00:00:00Z", "to_date": "2026-10-01T00:00:00Z"}, "invalid_date_range"),
    ],
)
def test_consistent_date_filter_rejection(env, endpoint, filters, code):
    clients, _ = env
    response = clients["caller"].get(endpoint, params=filters)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code


def test_literal_search_interest_stage_filters_and_export_agree(env):
    clients, _ = env
    c = clients["caller"]
    lead = make_lead(c, name="100% Customer_One", interests=["CRM Support", "50% off"])
    make_lead(c, name="Other Customer", phone="9810001235", interests=["Implementation"])
    for filters in [
        {"q": "%"},
        {"q": "_One"},
        {"interest": "support"},
        {"interest": "%"},
        {"stage": "new", "interest": "CRM"},
    ]:
        result = c.get("/api/leads", params=filters)
        assert result.status_code == 200, result.text
        assert [item["id"] for item in result.json()["items"]] == [lead["id"]]
        exported = c.get("/api/leads/export", params=filters)
        assert [row["name"] for row in csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))] == [lead["name"]]
    assert c.get("/api/leads?interest=nomatch").json()["total"] == 0
    assert clients["other"].get("/api/leads?interest=support").json()["total"] == 0


def test_history_more_than_500_stable_pagination_permissions_and_recording_link(env):
    clients, ids = env
    c = clients["caller"]
    lead = make_lead(c)
    timestamp = now()
    with SessionLocal.begin() as db:
        db.add_all(
            [
                Note(
                    org_id=ids["org"],
                    lead_id=lead["id"],
                    author_id=ids["caller"],
                    text=f"Context {index}",
                    created_at=timestamp,
                )
                for index in range(507)
            ]
        )
        for index, user in enumerate(["caller", "caller2"]):
            call = PhoneCall(
                org_id=ids["org"],
                lead_id=lead["id"],
                user_id=ids[user],
                device_id="qa",
                device_call_id=str(index),
                phone=lead["phone"],
                direction="outgoing",
                result="answered",
                duration=10,
                started_at=timestamp,
            )
            db.add(call)
            db.flush()
            db.add(
                Attachment(
                    org_id=ids["org"],
                    lead_id=lead["id"],
                    phone_call_id=call.id,
                    author_id=ids[user],
                    name=f"{user}.wav",
                    mime="audio/wav",
                    size=100,
                    storage_key=str(uuid4()),
                    digest=str(uuid4()),
                )
            )
    seen = []
    for page in range(1, 7):
        response = c.get(f"/api/leads/{lead['id']}/history", params={"page": page, "size": 100})
        assert response.status_code == 200, response.text
        h = response.json()
        assert h["pagination"]["totals"]["notes"] == 507
        seen += [note["id"] for note in h["notes"]]
        if page == 1:
            assert len(h["phone_calls"]) == 1
            assert h["phone_calls"][0]["recordings"][0]["name"] == "caller.wav"
            assert [f["name"] for f in h["files"]] == ["caller.wav"]
            assert "storage_key" not in str(h) and "sha256" not in str(h)
    assert len(seen) == len(set(seen)) == 507
    assert clients["caller2"].get(f"/api/leads/{lead['id']}/history?page=2").status_code == 404
    assert clients["other"].get(f"/api/leads/{lead['id']}/history").status_code == 404
    assert c.get(f"/api/leads/{lead['id']}/history?page=0").status_code == 422


def test_required_false_and_inactive_custom_field_cannot_be_added_later(env):
    clients, _ = env
    field = {"kind": "field", "key": "consent", "label": "Consent", "config": {"type": "boolean", "required": True}}
    response = clients["admin"].post("/api/definitions", json=field)
    assert response.status_code == 201
    lead = make_lead(clients["caller"], custom={"consent": False})
    assert clients["caller"].get("/api/leads/" + lead["id"]).json()["custom"]["consent"] is False
    assert (
        clients["admin"].put("/api/definitions/" + response.json()["id"], json={**field, "active": False}).status_code
        == 200
    )
    another = make_lead(clients["caller"], phone="9810001235")
    assert (
        clients["caller"].patch("/api/leads/" + another["id"], json={"custom": {"consent": False}}).status_code == 422
    )


@pytest.mark.parametrize("options", [[""], [" "], [" Yes"], ["Yes", "Yes"], ["x"] * 101, [42]])
def test_invalid_select_definitions_fail_before_persisting(env, options):
    clients, _ = env
    response = clients["admin"].post(
        "/api/definitions",
        json={
            "kind": "field",
            "key": "qa_select",
            "label": "QA select",
            "config": {"type": "select", "options": options},
        },
    )
    assert response.status_code == 422, response.text
    assert not any(d["key"] == "qa_select" for d in clients["caller"].get("/api/definitions").json())


@pytest.mark.parametrize("stage,closed", [("negotiation", False), ("archive", True)])
def test_outcomes_preserve_open_stages_and_reopen_closed_custom_stages(env, stage, closed):
    clients, _ = env
    response = clients["admin"].post(
        "/api/definitions",
        json={"kind": "stage", "key": stage, "label": stage.title(), "config": {"color": "#123456", "closed": closed}},
    )
    assert response.status_code == 201, response.text
    lead = make_lead(clients["caller"], stage=stage)
    response = clients["caller"].post(
        f"/api/leads/{lead['id']}/outcomes", json={"outcome": "not-picked", "duration": 0, "request_id": str(uuid4())}
    )
    assert response.status_code == 201, response.text
    assert clients["caller"].get("/api/leads/" + lead["id"]).json()["stage"] == ("qualified" if closed else stage)


def test_manager_audit_filter_precedes_pagination(env):
    clients, ids = env
    with SessionLocal.begin() as db:
        db.add(
            Audit(
                org_id=ids["org"],
                entity="lead",
                entity_id="qa",
                action="qa",
                summary="Visible operation",
                created_at=now() - timedelta(days=1),
            )
        )
        db.add_all(
            [
                Audit(
                    org_id=ids["org"],
                    entity="pay_profile",
                    entity_id=str(i),
                    action="qa",
                    summary="Sensitive compensation",
                )
                for i in range(60)
            ]
        )
    listed = clients["manager"].get("/api/audit?action=qa").json()
    assert len(listed) == 1 and listed[0]["summary"] == "Visible operation"
    exported = clients["manager"].get("/api/audit?action=qa&export=true").text
    assert "Visible operation" in exported and "Sensitive compensation" not in exported


def test_corrupt_provider_credential_does_not_break_other_integration_or_disconnect(env):
    clients, ids = env
    with SessionLocal.begin() as db:
        db.add(Integration(org_id=ids["org"], provider="indiamart", secret="invalid ciphertext", enabled=True))
    response = clients["admin"].get("/api/integrations")
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0]["state"] == "setup_required"
    assert clients["admin"].post("/api/integrations/indiamart/sync").status_code == 409
    assert clients["admin"].put("/api/integrations/indiamart", json={"enabled": False}).status_code == 200
    assert clients["admin"].put("/api/integrations/indiamart", json={"enabled": True}).status_code == 422
    assert clients["admin"].delete("/api/integrations/indiamart").status_code == 200
    assert (
        clients["admin"]
        .put("/api/integrations/indiamart", json={"enabled": True, "credential": "replacement-credential-123"})
        .status_code
        == 200
    )


def test_provider_long_identifiers_remain_distinct_and_oversize_batch_preserves_cursor(env, monkeypatch):
    clients, ids = env
    with SessionLocal.begin() as db:
        record = Integration(org_id=ids["org"], provider="indiamart", secret=encrypt("secret"))
        db.add(record)
        db.flush()
        items = [{"id": "prefix" * 30 + str(i), "name": f"Customer {i}", "phone": f"981000123{i}"} for i in range(2)]
        assert ingest(db, record, items)["imported"] == 2
        assert ingest(db, record, items)["duplicates"] == 2
        assert len(list(db.scalars(select(Provenance)))) == 2

        class Response:
            status_code = 200
            content = b"[]"

            def json(self):
                return {"CODE": 200, "RESPONSE": items * 5001}

        monkeypatch.setattr("app.integrations.httpx.Client.get", lambda *args, **kwargs: Response())
        with pytest.raises(ValueError, match="10,000"):
            poll_indiamart(db, record)
        assert record.last_sync is None
        assert len(list(db.scalars(select(Lead)))) == 2


def test_worker_slow_or_failed_org_does_not_stall_another(env, monkeypatch):
    _, ids = env
    from app.worker import tick

    progressed = threading.Event()

    def process(org):
        if org == ids["org"]:
            assert progressed.wait(2), "A slow org prevented the other org from starting"
            raise ValueError("simulated provider outage")
        progressed.set()

    monkeypatch.setattr("app.worker.process_organization", process)
    tick()
    assert progressed.is_set()


@pytest.mark.parametrize(
    "filters",
    [
        {"owner_id": True},
        {"from_date": "2026-11-01", "to_date": "2026-10-01"},
        {"from_date": "2026-10-01", "to_date": "2026-11-01T00:00:00Z"},
    ],
)
def test_invalid_saved_filter_types_ranges_are_rejected(env, filters):
    clients, _ = env
    response = clients["caller"].post(
        "/api/saved-views", json={"name": "Invalid view", "kind": "leads", "filters": filters}
    )
    assert response.status_code == 422, response.text


def test_submission_pagination_stable_and_scoped(env):
    clients, ids = env
    with SessionLocal.begin() as db:
        db.add_all(
            [
                TimeEntry(
                    org_id=ids["org"],
                    user_id=ids["caller"],
                    submitter_id=ids["caller"],
                    day=now().date() - timedelta(days=i),
                    hours=1,
                    category="calling",
                    description="QA pagination",
                    source="manual",
                )
                for i in range(105)
            ]
        )
    first = clients["caller"].get("/api/time-entries").json()
    second = clients["caller"].get("/api/time-entries?page=2").json()
    assert len(first) == 100 and len(second) == 5
    assert not set(x["id"] for x in first) & set(x["id"] for x in second)
    assert clients["caller2"].get("/api/time-entries?page=1").json() == []
    assert clients["other"].get("/api/time-entries?page=2").json() == []


@pytest.mark.parametrize("raw", [b"%PDF-1.4", b"%PDF-1.7\nnot a PDF\n%%EOF", b"%PDF-1.4\n% minimal document"])
def test_pdf_signatures_alone_do_not_pass_structure_validation(env, raw):
    clients, _ = env
    lead = make_lead(clients["caller"])
    response = clients["caller"].post(
        f"/api/leads/{lead['id']}/files", files={"file": ("broken.pdf", raw, "application/pdf")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_content"
    assert clients["caller"].get(f"/api/leads/{lead['id']}/history").json()["files"] == []


def test_encrypted_pdf_and_valid_pdf_round_trip_without_disclosing_storage(env):
    from pypdf import PdfWriter

    clients, _ = env
    lead = make_lead(clients["caller"])
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("private-document-password")
    raw = io.BytesIO()
    writer.write(raw)
    response = clients["caller"].post(
        f"/api/leads/{lead['id']}/files", files={"file": ("protected.pdf", raw.getvalue(), "application/pdf")}
    )
    assert response.status_code == 201, response.text
    assert "storage_key" not in response.json()
    downloaded = clients["caller"].get("/api/files/" + response.json()["id"])
    assert downloaded.content == raw.getvalue()


def test_retired_select_option_is_preserved_only_when_unchanged(env):
    clients, _ = env
    field = {
        "kind": "field",
        "key": "package",
        "label": "Package",
        "config": {"type": "select", "options": ["Premium"]},
    }
    response = clients["admin"].post("/api/definitions", json=field)
    assert response.status_code == 201
    lead = make_lead(clients["caller"], custom={"package": "Premium"})
    field["config"]["options"] = ["Enterprise"]
    assert clients["admin"].put("/api/definitions/" + response.json()["id"], json=field).status_code == 200
    edited = clients["caller"].patch("/api/leads/" + lead["id"], json={"city": "Pune"})
    assert edited.status_code == 200 and edited.json()["custom"] == {"package": "Premium"}
    another = make_lead(clients["caller"], phone="9810001235")
    assert (
        clients["caller"].patch("/api/leads/" + another["id"], json={"custom": {"package": "Premium"}}).status_code
        == 422
    )


@pytest.mark.parametrize(
    "start,end,hours",
    [
        ("2026-03-08T05:00:00+00:00", "2026-03-09T04:00:00+00:00", 23),
        ("2026-11-01T04:00:00+00:00", "2026-11-02T05:00:00+00:00", 25),
    ],
)
def test_dst_workplace_days_close_at_real_midnight_once(env, monkeypatch, start, end, hours):
    from datetime import datetime
    from app.models import Attendance

    clients, ids = env
    geo = {"latitude": 19.076, "longitude": 72.8777, "accuracy": 5}
    assert (
        clients["admin"]
        .put(
            "/api/settings",
            json={"workplace": {**geo, "name": "Office", "radius": 200, "timezone": "America/New_York"}},
        )
        .status_code
        == 200
    )
    instant = datetime.fromisoformat(start)
    cutoff = datetime.fromisoformat(end)
    monkeypatch.setattr("app.workforce.now", lambda: instant)
    response = clients["caller"].post("/api/attendance/check-in", json=geo)
    assert response.status_code == 201, response.text
    record = response.json()
    assert datetime.fromisoformat(record["cutoff"]) == cutoff
    monkeypatch.setattr("app.workforce.now", lambda: cutoff + timedelta(hours=2))
    closed = clients["caller"].post("/api/attendance/check-out")
    assert closed.status_code == 200
    assert datetime.fromisoformat(closed.json()["checked_out"]) == cutoff
    assert closed.json()["auto_closed"] is True
    assert clients["caller"].post("/api/attendance/check-out").status_code == 409
    with SessionLocal() as db:
        entries = list(db.scalars(select(TimeEntry).where(TimeEntry.source_id == record["id"])))
        assert len(entries) == 1 and entries[0].hours == hours and entries[0].state == "pending"
        assert db.get(Attendance, record["id"]).day == instant.date()


@pytest.mark.parametrize("commit_failure", [False, True])
def test_save_headers_are_sent_only_after_database_commit_or_rollback(env, monkeypatch, commit_failure):
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import IntegrityError
    from app.main import app

    clients, _ = env
    lead = make_lead(clients["caller"])
    path = f"/api/leads/{lead['id']}/notes"
    observed = []
    if commit_failure:

        def fail_commit(self):
            raise IntegrityError("private SQL must remain hidden", {}, Exception("forced commit failure"))

        monkeypatch.setattr(SessionLocal.class_, "commit", fail_commit)

    class ObserveHeaders:
        async def __call__(self, scope, receive, send):
            async def inspect(message):
                if message["type"] == "http.response.start" and scope.get("path") == path:
                    with SessionLocal() as db:
                        observed.append(
                            bool(
                                db.scalar(
                                    select(Note).where(
                                        Note.lead_id == lead["id"], Note.text == "Durable before success"
                                    )
                                )
                            )
                        )
                await send(message)

            await app(scope, receive, inspect)

    with TestClient(ObserveHeaders(), raise_server_exceptions=False, headers=dict(clients["caller"].headers)) as client:
        response = client.post(path, json={"text": "Durable before success"})
    assert response.status_code == (409 if commit_failure else 201), response.text
    assert observed == [not commit_failure]
    if commit_failure:
        assert response.json()["error"]["code"] == "conflict"
        assert "private SQL" not in response.text and "forced commit failure" not in response.text


def test_non_ascii_webhook_token_is_rejected_as_unauthorized_not_an_internal_error(env):
    clients, ids = env
    configured = clients["admin"].put(
        "/api/integrations/justdial", json={"credential": "valid-ascii-credential-123", "enabled": True}
    )
    assert configured.status_code == 200
    response = clients["other"].post(
        "/api/webhooks/justdial/" + ids["org"],
        json={"name": "Untrusted lead", "mobile": "9810001234"},
        headers={"X-Webhook-Token": b"\xff" * 20},
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "invalid_webhook_token"
    assert clients["admin"].get("/api/leads").json()["total"] == 0
