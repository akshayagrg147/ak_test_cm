from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal, now
from app.main import app
from app.models import FieldHandoff, Lead, Note, SiteVisit, Task, User
from conftest import PASSWORD, make_lead
from test_real_estate import booking_payload, inventory
from test_recording_formats import native_recording, recording_call


@pytest.fixture()
def field_env(env):
    clients, ids = env
    assert clients["admin"].post("/api/real-estate/setup").status_code == 200
    created = []
    for key, suffix in [("field", "81"), ("field2", "82")]:
        phone = "+9199000080" + suffix
        response = clients["admin"].post(
            "/api/team",
            json={"name": key.title() + " Executive", "phone": phone, "role": "field_executive", "password": PASSWORD},
        )
        assert response.status_code == 201, response.text
        ids[key] = response.json()["id"]
        client = TestClient(app)
        auth = client.post("/api/auth/login", json={"phone": phone, "password": PASSWORD})
        assert auth.status_code == 200
        client.headers.update(
            {"Authorization": "Bearer " + auth.json()["access_token"], "X-Requested-With": "TalkoCRM"}
        )
        clients[key] = client
        created.append(client)
    prop = inventory(clients["admin"])
    yield clients, ids, prop
    for client in created:
        client.close()


def payload(lead, prop, executive, **extra):
    return {
        "lead_id": lead["id"],
        "property_id": prop["id"],
        "executive_id": executive,
        "starts_at": (now() + timedelta(hours=2)).isoformat(),
        "duration_minutes": 60,
        "brief": "Client confirmed 3BHK. Budget and financing are recorded in the property brief.",
        "meeting_point": "Main gate, Panipat property office",
        "client_confirmed": True,
        "request_id": str(uuid4()),
        **extra,
    }


def create(c, ids, prop, **extra):
    lead = make_lead(c["caller"])
    data = payload(lead, prop, ids["field"], **extra)
    response = c["caller"].post("/api/field-work", json=data)
    assert response.status_code == 201, response.text
    return lead, response.json(), data


def change(client, item, action, **extra):
    return client.patch("/api/field-work/" + item["id"], json={"version": item["version"], "action": action, **extra})


def accept(c, item):
    response = change(c["field"], item, "accept")
    assert response.status_code == 200, response.text
    return response.json()


def test_handoff_preserves_caller_and_grants_only_assigned_executive_history(field_env):
    c, ids, prop = field_env
    lead, call_id = recording_call(c["caller"])
    raw = native_recording()
    uploaded = c["caller"].post(
        f"/api/leads/{lead['id']}/files", data={"phone_call_id": call_id}, files={"file": ("discussion.m4a", raw)}
    )
    assert uploaded.status_code == 201
    file_id = uploaded.json()["id"]
    assert c["field"].get(f"/api/leads/{lead['id']}").status_code == 404
    response = c["caller"].post("/api/field-work", json=payload(lead, prop, ids["field"]))
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["status"] == "pending" and item["visit"]["assignee_id"] == ids["field"]
    for role in ["caller", "field"]:
        assert c[role].get(f"/api/leads/{lead['id']}").json()["owner_id"] == ids["caller"]
        history = c[role].get(f"/api/leads/{lead['id']}/history").json()
        assert history["phone_calls"][0]["id"] == call_id
        assert c[role].get("/api/files/" + file_id).content == raw
        assert c[role].delete("/api/files/" + file_id).status_code == 403
        assert c[role].get("/api/site-visits").json()["total"] == 1
    for role in ["field2", "caller2", "other"]:
        assert c[role].get(f"/api/leads/{lead['id']}/history").status_code == 404
        assert c[role].get("/api/files/" + file_id).status_code == 404
        assert c[role].get("/api/field-work").json()["items"] == []
    assert c["caller"].get("/api/phone-calls/contacts").json()["items"][0]["id"] == lead["id"]
    assert c["field"].get("/api/phone-calls/contacts").status_code == 403
    assert c["field"].get("/api/phone-calls").json()["total"] == 1
    assert c["field2"].get("/api/phone-calls").json()["total"] == 0
    alerts = c["field"].get("/api/notifications").json()
    assert any(a["title"] == "Accept client handoff" for a in alerts)


def test_confirmation_role_and_cross_company_validation(field_env):
    c, ids, prop = field_env
    lead = make_lead(c["caller"])
    data = payload(lead, prop, ids["field"])
    for role in ["field", "owner"]:
        assert c[role].post("/api/field-work", json=data).status_code == 403
    assert c["caller2"].post("/api/field-work", json=data).status_code == 404
    assert c["caller"].post("/api/field-work", json={**data, "client_confirmed": False}).status_code == 422
    for executive in [ids["manager"], ids["caller"], ids["other"]]:
        assert c["caller"].post("/api/field-work", json={**data, "executive_id": executive}).status_code in {404, 422}
    assert c["admin"].patch("/api/team/" + ids["field"], json={"active": False}).status_code == 200
    assert c["caller"].post("/api/field-work", json=data).status_code == 422
    for values in [
        {"starts_at": "2026-10-25T10:00:00"},
        {"brief": " "},
        {"meeting_point": " "},
        {"duration_minutes": 14},
        {"request_id": "short"},
    ]:
        assert c["caller"].post("/api/field-work", json={**data, **values}).status_code == 422


def test_idempotent_handoff_and_conflicting_or_duplicate_requests(field_env):
    c, ids, prop = field_env
    lead, item, data = create(c, ids, prop)
    assert c["caller"].post("/api/field-work", json=data).json()["id"] == item["id"]
    assert c["caller"].post("/api/field-work", json={**data, "brief": "Different discussion"}).status_code == 409
    assert c["caller"].post("/api/field-work", json={**data, "request_id": str(uuid4())}).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SiteVisit)) == 1
        assert db.get(Lead, lead["id"]).stage == "site_visit"


def test_schedule_overlap_adjacent_slots_property_and_closed_lead_guards(field_env):
    c, ids, prop = field_env
    _, item, _ = create(c, ids, prop)
    second = make_lead(c["caller"], phone="+919810002222")
    data = payload(second, prop, ids["field"], starts_at=item["visit"]["starts_at"])
    assert c["caller"].post("/api/field-work", json=data).status_code == 409
    start = datetime.fromisoformat(item["visit"]["starts_at"]) + timedelta(hours=1)
    assert c["caller"].post("/api/field-work", json={**data, "starts_at": start.isoformat()}).status_code == 201
    third = make_lead(c["caller"], phone="+919810002223", dnd=True)
    assert c["caller"].post("/api/field-work", json=payload(third, prop, ids["field2"])).status_code == 409
    assert (
        c["admin"]
        .put(
            "/api/properties/" + prop["id"],
            json={
                **{k: v for k, v in prop.items() if k not in {"id", "org_id", "created_at", "archived", "files"}},
                "status": "off-market",
            },
        )
        .status_code
        == 200
    )
    fourth = make_lead(c["caller"], phone="+919810002224")
    assert c["caller"].post("/api/field-work", json=payload(fourth, prop, ids["field2"])).status_code == 409


def test_acceptance_and_stale_version_cannot_duplicate_changes(field_env):
    c, ids, prop = field_env
    _, item, _ = create(c, ids, prop)
    assert change(c["caller"], item, "accept").status_code == 403
    assert change(c["field2"], item, "accept").status_code == 404
    accepted = accept(c, item)
    assert accepted["accepted_at"] and accepted["version"] == item["version"] + 1
    assert change(c["field"], item, "accept").status_code == 409
    assert (
        change(
            c["field"],
            accepted,
            "visit_outcome",
            visit_status="completed",
            next_step="closed",
            feedback="Client attended",
        ).status_code
        == 409
    )
    assert (
        change(
            c["caller"],
            accepted,
            "visit_outcome",
            visit_status="completed",
            next_step="closed",
            feedback="Client attended",
        ).status_code
        == 403
    )


def test_visit_followup_task_and_booking_review_form_complete_flow(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop, starts_at=(now() - timedelta(minutes=1)).isoformat())
    item = accept(c, item)
    response = change(
        c["field"],
        item,
        "visit_outcome",
        visit_status="completed",
        feedback="Client liked the apartment, wants loan details.",
        next_step="follow_up",
        next_action="Confirm loan documents",
        follow_up_at=(now() + timedelta(hours=3)).isoformat(),
    )
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["visit"]["status"] == "completed" and item["status"] == "follow_up"
    tasks = c["field"].get("/api/tasks").json()
    assert len(tasks) == 1 and tasks[0]["field_handoff_id"] == item["id"] and tasks[0]["owner_id"] == ids["field"]
    assert c["field"].delete("/api/tasks/" + item["task_id"]).status_code == 409
    assert c["caller"].get("/api/tasks").json() == []
    assert "Confirm loan documents" in c["field"].get(f"/api/leads/{lead['id']}/history").json()["notes"][0]["text"]
    ready = change(
        c["field"], item, "follow_up", feedback="Loan approved; client wants to reserve.", next_step="ready_for_booking"
    )
    assert ready.status_code == 200, ready.text
    item = ready.json()
    assert item["task_id"] is None and c["field"].get("/api/tasks").json()[0]["state"] == "completed"
    assert any(a["title"] == "Client ready for booking" for a in c["manager"].get("/api/notifications").json())
    booking = c["manager"].post("/api/bookings", json=booking_payload(lead, prop, ids["field"]))
    assert booking.status_code == 201
    assert c["field"].post("/api/bookings", json=booking_payload(lead, prop, ids["field"])).status_code == 403
    booked = c["manager"].patch(
        "/api/bookings/" + booking.json()["id"], json={"status": "booked", "notes": "Client confirmed reservation"}
    )
    assert booked.status_code == 200
    current = c["field"].get("/api/field-work").json()["items"][0]
    assert current["status"] == "closed" and "Booking confirmed" in current["feedback"]
    assert change(c["field"], current, "follow_up", next_step="closed", feedback="Changed mind").status_code == 409


def test_early_attendance_retains_schedule_and_actual_time_with_atomic_followup(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    item = accept(c, item)
    scheduled = item["visit"]["starts_at"]
    actual = now() - timedelta(minutes=30)
    values = {
        "visit_status": "completed",
        "early_visit_confirmed": True,
        "actual_started_at": actual.isoformat(),
        "feedback": "Client visited earlier and asked about financing.",
        "next_step": "follow_up",
        "next_action": "Confirm finance documents",
        "follow_up_at": (now() - timedelta(minutes=1)).isoformat(),
    }
    assert change(c["field"], item, "visit_outcome", **values).status_code == 422
    unchanged = c["field"].get("/api/field-work").json()["items"][0]
    assert unchanged["visit"]["actual_started_at"] is None
    assert unchanged["visit"]["status"] == "scheduled" and unchanged["version"] == item["version"]
    assert c["field"].get("/api/tasks").json() == []
    values["follow_up_at"] = (now() + timedelta(hours=2)).isoformat()
    assert change(c["caller"], item, "visit_outcome", **values).status_code == 403
    assert change(c["field2"], item, "visit_outcome", **values).status_code == 404
    response = change(c["field"], item, "visit_outcome", **values)
    assert response.status_code == 200, response.text
    completed = response.json()
    assert datetime.fromisoformat(completed["visit"]["starts_at"]) == datetime.fromisoformat(scheduled)
    assert completed["visit"]["status"] == "completed"
    assert datetime.fromisoformat(completed["visit"]["actual_started_at"]) == actual
    assert completed["status"] == "follow_up" and completed["task_id"]
    assert change(c["field"], item, "visit_outcome", **values).status_code == 409
    assert len(c["field"].get("/api/tasks").json()) == 1
    visits = c["caller"].get("/api/site-visits").json()["items"]
    assert datetime.fromisoformat(visits[0]["actual_started_at"]) == actual
    history = c["caller"].get(f"/api/leads/{lead['id']}/history").json()
    event = next(a for a in history["activity"] if a["action"] == "field_handoff_visit_outcome")
    assert datetime.fromisoformat(event["details"]["actual_started_at"]) == actual
    assert datetime.fromisoformat(event["details"]["scheduled_starts_at"]) == datetime.fromisoformat(scheduled)
    with pytest.raises(RuntimeError, match="actual visit times"):
        command.downgrade(Config("alembic.ini"), "0008")
    command.check(Config("alembic.ini"))


def test_early_attendance_requires_real_past_time_and_cannot_mark_future_no_show(field_env):
    c, ids, prop = field_env
    _, item, _ = create(c, ids, prop)
    item = accept(c, item)
    base = {"visit_status": "completed", "next_step": "closed", "feedback": "Client attended before schedule"}
    for extra, status in [
        ({}, 409),
        ({"early_visit_confirmed": True}, 422),
        ({"early_visit_confirmed": True, "actual_started_at": (now() + timedelta(minutes=5)).isoformat()}, 422),
        ({"early_visit_confirmed": True, "actual_started_at": item["visit"]["starts_at"]}, 422),
        ({"early_visit_confirmed": True, "actual_started_at": "2026-10-25T10:00:00"}, 422),
        ({"actual_started_at": (now() - timedelta(minutes=5)).isoformat()}, 409),
        ({"visit_status": "no-show"}, 409),
        (
            {
                "visit_status": "no-show",
                "early_visit_confirmed": True,
                "actual_started_at": (now() - timedelta(minutes=5)).isoformat(),
            },
            422,
        ),
    ]:
        response = change(c["field"], item, "visit_outcome", **{**base, **extra})
        assert response.status_code == status, response.text
    assert (
        change(c["field"], item, "close", feedback="Close without visit", early_visit_confirmed=True).status_code == 422
    )
    unchanged = c["field"].get("/api/field-work").json()["items"][0]
    assert unchanged["visit"]["status"] == "scheduled" and unchanged["visit"]["actual_started_at"] is None
    assert unchanged["version"] == item["version"]


def test_missing_next_step_future_date_and_no_show_are_validated_atomically(field_env):
    c, ids, prop = field_env
    _, item, _ = create(c, ids, prop, starts_at=(now() - timedelta(minutes=1)).isoformat())
    assert (
        change(
            c["field"], item, "visit_outcome", visit_status="completed", next_step="closed", feedback="Client attended"
        ).status_code
        == 409
    )
    item = accept(c, item)
    base = {"visit_status": "completed", "feedback": "Client attended", "next_step": "follow_up"}
    for extra in [
        {},
        {"follow_up_at": (now() - timedelta(hours=1)).isoformat(), "next_action": "Discuss price"},
        {"follow_up_at": "2026-10-26T10:00:00", "next_action": "Discuss price"},
    ]:
        assert change(c["field"], item, "visit_outcome", **{**base, **extra}).status_code == 422
    assert (
        change(
            c["field"],
            item,
            "visit_outcome",
            visit_status="no-show",
            next_step="ready_for_booking",
            feedback="Client absent",
        ).status_code
        == 422
    )
    with SessionLocal() as db:
        assert db.get(SiteVisit, item["visit_id"]).status == "scheduled"
        assert db.scalar(select(func.count()).select_from(Task)) == 0
    response = change(
        c["field"],
        item,
        "visit_outcome",
        visit_status="no-show",
        next_step="follow_up",
        feedback="Client could not attend",
        next_action="Agree another visit",
        follow_up_at=(now() + timedelta(days=1)).isoformat(),
    )
    assert response.status_code == 200
    item = response.json()
    response = change(
        c["caller"],
        item,
        "reschedule",
        starts_at=(now() + timedelta(days=2)).isoformat(),
        feedback="Client confirmed new date",
        meeting_point="Meet at office reception",
    )
    assert response.status_code == 200
    assert response.json()["visit_id"] != item["visit_id"] and response.json()["status"] == "accepted"
    assert c["field"].get("/api/tasks").json()[0]["state"] == "cancelled"


def test_reassignment_revokes_history_and_member_removal_requires_resolution(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    for body in [{"active": False}, {"role": "manager"}]:
        assert c["admin"].patch("/api/team/" + ids["field"], json=body).status_code == 409
    assert c["admin"].delete("/api/team/" + ids["field"], params={"confirmation": "Field Executive"}).status_code == 409
    assert change(c["caller"], item, "reassign", executive_id=ids["field2"], feedback="Change agent").status_code == 403
    response = change(c["manager"], item, "reassign", executive_id=ids["field2"], feedback="Executive unavailable")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["status"] == "pending" and item["visit"]["assignee_id"] == ids["field2"]
    assert c["field"].get(f"/api/leads/{lead['id']}/history").status_code == 404
    assert c["field"].get("/api/field-work").json()["items"] == []
    assert c["field2"].get(f"/api/leads/{lead['id']}").status_code == 200
    assert c["admin"].patch("/api/team/" + ids["field"], json={"active": False}).status_code == 200


def test_cancellation_releases_slot_and_allows_new_handoff(field_env):
    c, ids, prop = field_env
    lead, item, data = create(c, ids, prop)
    cancelled = change(c["caller"], item, "cancel", feedback="Client cancelled appointment")
    assert cancelled.status_code == 200
    assert cancelled.json()["visit"]["status"] == "cancelled"
    response = c["caller"].post(
        "/api/field-work", json={**data, "executive_id": ids["field2"], "request_id": str(uuid4())}
    )
    assert response.status_code == 201
    assert c["field"].get(f"/api/leads/{lead['id']}").status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(FieldHandoff).where(FieldHandoff.current.is_(True))) == 1
    assert c["caller"].post("/api/field-work", json=data).json()["id"] == item["id"]


def test_generic_visit_tasks_and_archive_cannot_bypass_field_work(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    assert (
        c["admin"]
        .patch("/api/site-visits/" + item["visit_id"], json={"status": "cancelled", "feedback": "Try generic"})
        .status_code
        == 409
    )
    assert c["admin"].delete("/api/leads/" + lead["id"], params={"confirmation": lead["name"]}).status_code == 409
    second = make_lead(c["caller"], phone="+919810009998")
    assert c["admin"].post(f"/api/leads/{lead['id']}/merge/{second['id']}").status_code == 409
    assert (
        c["field"].post("/api/leads/assign", json={"lead_ids": [lead["id"]], "owner_id": ids["caller2"]}).status_code
        == 403
    )


def test_concurrent_accept_and_follow_up_create_exactly_one_task(field_env):
    c, ids, prop = field_env
    _, item, _ = create(c, ids, prop, starts_at=(now() - timedelta(minutes=1)).isoformat())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: change(c["field"], item, "accept"), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    item = next(r.json() for r in results if r.status_code == 200)
    values = {
        "visit_status": "completed",
        "next_step": "follow_up",
        "feedback": "Client attended",
        "next_action": "Review loan file",
        "follow_up_at": (now() + timedelta(hours=1)).isoformat(),
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: change(c["field"], item, "visit_outcome", **values), range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Task)) == 1
        assert db.scalar(select(func.count()).select_from(Note)) == 1


def test_field_role_cannot_read_other_team_records_or_admin_areas(field_env):
    c, ids, _ = field_env
    make_lead(c["caller"])
    assert c["field"].get("/api/leads").json()["items"] == []
    assert c["field"].get("/api/analytics").json()["metrics"]["leads"] == 0
    assert c["field"].get("/api/time-entries").json() == []
    assert c["field"].get("/api/attendance?team=true").json() == []
    for path in [
        "/api/team",
        "/api/audit",
        "/api/payroll?month=2026-10",
        "/api/billing",
        "/api/bookings",
        "/api/integrations",
    ]:
        assert c["field"].get(path).status_code == 403, path
    assert (
        c["field"].post("/api/phone-calls/sync", json={"device_id": "field-unsupported", "calls": []}).status_code
        == 403
    )
    own = make_lead(c["field"], phone="+919810009997")
    assert own["owner_id"] == ids["field"]
    login_as = c["admin"].post("/api/team/" + ids["field"] + "/login-as")
    assert login_as.status_code == 200 and login_as.json()["role"] == "field_executive"
    assert "password_hash" not in str(login_as.json())


def test_field_handoff_migration_guard_retains_history(field_env):
    c, ids, prop = field_env
    create(c, ids, prop)
    with pytest.raises(RuntimeError, match="field work or field-executive"):
        command.downgrade(Config("alembic.ini"), "0007")
    command.check(Config("alembic.ini"))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(FieldHandoff)) == 1
        assert db.get(User, ids["field"]).role == "field_executive"


def test_concurrent_create_same_request_acknowledges_one_visit(field_env):
    c, ids, prop = field_env
    lead = make_lead(c["caller"])
    data = payload(lead, prop, ids["field"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: c["caller"].post("/api/field-work", json=data), range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(FieldHandoff)) == 1
        assert db.scalar(select(func.count()).select_from(SiteVisit)) == 1


def test_closed_outcome_and_dnd_require_resolving_field_work(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    response = c["caller"].post(
        f"/api/leads/{lead['id']}/outcomes",
        json={
            "outcome": "lost",
            "notes": "Client changed plans",
            "manager_id": ids["manager"],
            "request_id": "lost-before-field-close",
        },
    )
    assert response.status_code == 409
    assert c["caller"].patch("/api/leads/" + lead["id"], json={"dnd": True}).status_code == 200
    item = accept(c, item)
    assert (
        change(
            c["field"],
            item,
            "reschedule",
            starts_at=(now() + timedelta(days=1)).isoformat(),
            feedback="Try contact again",
        ).status_code
        == 409
    )
    cancelled = change(c["caller"], item, "cancel", feedback="Client asked not to be contacted")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


def test_reassignment_clashes_and_private_tasks_are_not_leaked(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    other_lead = make_lead(c["caller2"], phone="+919810009111")
    data = payload(other_lead, prop, ids["field2"], starts_at=item["visit"]["starts_at"])
    assert c["caller2"].post("/api/field-work", json=data).status_code == 201
    assert (
        change(
            c["manager"], item, "reassign", executive_id=ids["field2"], feedback="Overlapping reassignment"
        ).status_code
        == 409
    )
    assert c["field"].get("/api/field-work?status=not-a-status").status_code == 422
    assert c["field"].get("/api/field-work?due=not-a-due").status_code == 422
    private = c["caller"].post(
        "/api/tasks",
        json={
            "title": "Caller's private reminder",
            "lead_id": lead["id"],
            "due_at": (now() + timedelta(hours=1)).isoformat(),
        },
    )
    assert private.status_code == 201
    assert c["field"].get(f"/api/leads/{lead['id']}/history").json()["tasks"] == []
    assert c["field"].get("/api/tasks").json() == []
    assert c["field"].delete("/api/tasks/" + private.json()["id"]).status_code == 404
    assert c["field"].get("/api/leads/export").status_code == 200
    assert other_lead["phone"] not in c["field"].get("/api/leads/export").text


def test_caller_call_sync_continues_after_field_assignment(field_env):
    c, ids, prop = field_env
    lead, _, _ = create(c, ids, prop)
    body = {
        "device_id": "preserved-caller-contract",
        "calls": [
            {
                "device_call_id": "after-handoff",
                "phone": lead["phone"],
                "direction": "incoming",
                "result": "answered",
                "started_at": now().isoformat(),
                "duration": 30,
            }
        ],
    }
    first = c["caller"].post("/api/phone-calls/sync", json=body)
    assert first.status_code == 200 and first.json()["created"] == 1
    assert c["caller"].post("/api/phone-calls/sync", json=body).json()["updated"] == 1
    assert (
        c["field"].get(f"/api/leads/{lead['id']}/history").json()["phone_calls"][0]["id"]
        == first.json()["entries"][0]["call_id"]
    )
