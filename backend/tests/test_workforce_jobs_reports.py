from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import SessionLocal, now
from app.models import Attendance, AutomationRun, Job, Lead, Leave, Note, TimeEntry
from app.worker import process_organization, tick
from app.workforce import distance
from conftest import make_lead

GEO = {"latitude": 19.076, "longitude": 72.8777, "accuracy": 5}


@pytest.mark.parametrize(
    "body,code",
    [
        ({"latitude": 91, "longitude": 72, "accuracy": 5}, "validation_error"),
        ({"latitude": 19.076, "longitude": 72.8777, "accuracy": 300}, "location_inaccurate"),
        ({"latitude": 20, "longitude": 72, "accuracy": 5}, "outside_workplace"),
        ({"latitude": 19, "longitude": 72, "accuracy": -1}, "validation_error"),
    ],
)
def test_invalid_geofence(env, body, code):
    c, _ = env
    r = c["caller"].post("/api/attendance/check-in", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_checkin_explicit_concurrent_boundary_and_checkout(env):
    c, ids = env
    assert c["caller"].get("/api/attendance").json() == []
    assert c["caller"].post("/api/attendance/check-out").status_code == 409
    # Compute a 200 m due-north boundary point using the backend's Earth radius.
    import math

    geo = {**GEO, "latitude": GEO["latitude"] + math.degrees(200 / 6371000)}
    assert abs(distance(GEO["latitude"], GEO["longitude"], geo["latitude"], geo["longitude"]) - 200) < 0.001
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: c["caller"].post("/api/attendance/check-in", json=geo), range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    r = c["caller"].post("/api/attendance/check-out")
    assert r.status_code == 200
    assert r.json()["checked_out"] is not None
    assert c["caller"].post("/api/attendance/check-out").status_code == 409
    assert c["caller"].get("/api/time-entries").json() == []  # Too short to count.
    assert c["caller"].get("/api/attendance?team=true").json()[0]["user_id"] == ids["caller"]


def test_no_workplace_and_timezone_payloads(env):
    c, _ = env
    assert c["other"].post("/api/attendance/check-in", json=GEO).status_code == 409
    for radius in [24, 5001]:
        assert (
            c["admin"]
            .put(
                "/api/settings",
                json={"workplace": {**GEO, "name": "Office", "radius": radius, "timezone": "Asia/Kolkata"}},
            )
            .status_code
            == 422
        )
    assert (
        c["admin"]
        .put("/api/settings", json={"workplace": {**GEO, "name": "Office", "radius": 200, "timezone": "Invalid/Zone"}})
        .status_code
        == 422
    )
    assert c["admin"].put("/api/settings", json={"weekdays": [0, 0]}).status_code == 422


def test_midnight_catchup_idempotency_and_manual_worker_race(env):
    c, ids = env
    # Deliberately an old workplace day; cut-off is 00:00 IST / previous UTC 18:30.
    start = datetime(2026, 9, 1, 3, 30, tzinfo=timezone.utc)
    cutoff = datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc)
    with SessionLocal.begin() as db:
        record = Attendance(
            org_id=ids["org"],
            user_id=ids["caller"],
            day=date(2026, 9, 1),
            checked_in=start,
            cutoff=cutoff,
            location=GEO,
        )
        db.add(record)
        db.flush()
        record_id = record.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(process_organization, ids["org"]),
            pool.submit(lambda: c["caller"].post("/api/attendance/check-out")),
        ]
        for r in results:
            r.result()
    process_organization(ids["org"])
    with SessionLocal() as db:
        record = db.get(Attendance, record_id)
        entries = list(db.scalars(select(TimeEntry).where(TimeEntry.source_id == record_id)))
        assert record.checked_out == cutoff and record.auto_closed
        assert len(entries) == 1 and entries[0].hours == Decimal("15.0000") and entries[0].state == "pending"


def test_time_submission_review_boundaries_and_daily_limit(env):
    c, ids = env
    day = now().date().isoformat()
    r = c["caller"].post(
        "/api/time-entries",
        json={"day": day, "hours": "8.25", "description": "Calling customers", "category": "calling"},
    )
    assert r.status_code == 201, r.text
    record = r.json()["id"]
    assert c["caller"].post("/api/time-entries/" + record + "/review", json={"state": "approved"}).status_code == 403
    assert c["manager"].post("/api/time-entries/" + record + "/review", json={"state": "approved"}).status_code == 200
    assert c["admin"].post("/api/time-entries/" + record + "/review", json={"state": "approved"}).status_code == 409
    own = (
        c["manager"]
        .post("/api/time-entries", json={"day": day, "hours": 2, "description": "Team planning", "category": "admin"})
        .json()
    )
    assert (
        c["manager"].post("/api/time-entries/" + own["id"] + "/review", json={"state": "approved"}).status_code == 403
    )
    assert c["admin"].post("/api/time-entries/" + own["id"] + "/review", json={"state": "approved"}).status_code == 200
    assert (
        c["admin"]
        .post("/api/time-entries", json={"day": day, "hours": 2, "description": "Own admin work", "category": "admin"})
        .status_code
        == 403
    )
    assert (
        c["caller"]
        .post(
            "/api/time-entries",
            json={
                "user_id": ids["caller2"],
                "day": day,
                "hours": 2,
                "description": "Forged work",
                "category": "calling",
            },
        )
        .status_code
        == 403
    )
    assert (
        c["caller"]
        .post(
            "/api/time-entries", json={"day": day, "hours": 20, "description": "Too many hours", "category": "calling"}
        )
        .status_code
        == 422
    )
    assert (
        c["caller"]
        .post(
            "/api/time-entries",
            json={"day": (now().date() + timedelta(days=3)).isoformat(), "hours": 1, "description": "Future work"},
        )
        .status_code
        == 422
    )


def test_leave_overlap_concurrency_cross_month_and_self_review(env):
    c, ids = env
    body = {"starts_on": "2026-09-30", "ends_on": "2026-10-03", "kind": "planned", "reason": "Family holiday"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: c["manager"].post("/api/leave", json=body), range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    record = next(r.json() for r in responses if r.status_code == 201)
    assert c["manager"].post("/api/leave/" + record["id"] + "/review", json={"state": "approved"}).status_code == 403
    assert c["admin"].post("/api/leave/" + record["id"] + "/review", json={"state": "approved"}).status_code == 200
    assert (
        c["manager"].post("/api/leave", json={**body, "starts_on": "2026-10-04", "ends_on": "2026-10-03"}).status_code
        == 422
    )
    assert c["other"].post("/api/leave/" + record["id"] + "/review", json={"state": "approved"}).status_code == 404


def test_payroll_decimal_source_overlap_and_schedule(env):
    c, ids = env
    assert (
        c["admin"]
        .put("/api/payroll/profiles/" + ids["caller"], json={"hourly_rate": "101.15", "daily_target": "8"})
        .status_code
        == 200
    )
    c["admin"].post("/api/schedule-exceptions", json={"day": "2026-10-02", "working": False, "label": "Holiday"})
    c["admin"].post(
        "/api/schedule-exceptions", json={"day": "2026-10-03", "working": True, "label": "Working Saturday"}
    )
    with SessionLocal.begin() as db:
        for source, hours, state, source_id in [
            ("manual", "4.125", "approved", None),
            ("attendance", "8", "approved", "attendance-a"),
            ("manual", "2", "pending", None),
            ("manual", "5", "rejected", None),
        ]:
            db.add(
                TimeEntry(
                    org_id=ids["org"],
                    user_id=ids["caller"],
                    day=date(2026, 10, 1),
                    hours=Decimal(hours),
                    category="calling",
                    description="Fixture work",
                    source=source,
                    state=state,
                    source_id=source_id,
                )
            )
        db.add(
            Leave(
                org_id=ids["org"],
                user_id=ids["caller"],
                starts_on=date(2026, 9, 30),
                ends_on=date(2026, 10, 3),
                kind="planned",
                reason="Approved leave",
                state="approved",
            )
        )
    r = c["admin"].get("/api/payroll?month=2026-10")
    assert r.status_code == 200
    row = next(r for r in r.json()["items"] if r["user_id"] == ids["caller"])
    assert row["approved_hours"] == "8.00" and row["pending_hours"] == "2.00"
    assert (
        row["estimated_pay"] == "809.20"
        and row["working_days"] == 22
        and row["approved_leave_days"] == 2
        and row["target_hours"] == "160.00"
    )
    assert c["admin"].get("/api/payroll?month=2026-13").status_code == 422
    assert "101.15" in c["admin"].get("/api/payroll/export?month=2026-10").text
    assert "hourly_rate" not in str(c["manager"].get("/api/team").json())


@pytest.mark.parametrize(
    "trigger", ["lead_created", "lead_assigned", "status_changed", "callback_due", "task_completed"]
)
def test_every_automation_trigger_is_executed_once(env, trigger):
    c, ids = env
    rule = c["admin"].post(
        "/api/automations",
        json={
            "name": "Follow the next step",
            "trigger": trigger,
            "conditions": {},
            "action": "add_note",
            "config": {"text": "Created by automation"},
            "enabled": True,
        },
    )
    assert rule.status_code == 201
    lead = make_lead(c["caller"])
    if trigger == "lead_assigned":
        c["admin"].post("/api/leads/assign", json={"lead_ids": [lead["id"]], "owner_id": ids["caller2"]})
    if trigger == "status_changed":
        c["caller"].post(
            "/api/leads/" + lead["id"] + "/outcomes", json={"outcome": "converted", "request_id": "auto-status-change"}
        )
    if trigger == "callback_due":
        with SessionLocal.begin() as db:
            db.get(Lead, lead["id"]).follow_up = now() - timedelta(minutes=1)
    if trigger == "task_completed":
        c["caller"].post(
            "/api/tasks",
            json={
                "title": "Complete this step",
                "lead_id": lead["id"],
                "state": "completed",
                "due_at": now().isoformat(),
            },
        )
    process_organization(ids["org"])
    process_organization(ids["org"])
    with SessionLocal() as db:
        notes = list(db.scalars(select(Note).where(Note.lead_id == lead["id"], Note.text == "Created by automation")))
        # self-created leads create one assignment, then explicit assignment creates a second event.
        assert len(notes) == (2 if trigger == "lead_assigned" else 1)
        assert all(r.state == "success" for r in db.scalars(select(AutomationRun)))


def test_automation_manager_inactive_failure_visibility_and_no_recursion(env):
    c, ids = env
    c["admin"].post(
        "/api/automations",
        json={
            "name": "Route to manager",
            "trigger": "lead_created",
            "action": "assign_manager",
            "config": {"manager_id": ids["manager"]},
        },
    )
    make_lead(c["caller"])
    c["admin"].patch("/api/team/" + ids["manager"], json={"active": False})
    process_organization(ids["org"])
    runs = c["admin"].get("/api/automations").json()["runs"]
    assert len(runs) == 1 and runs[0]["state"] == "failed" and "no longer active" in runs[0]["error"]
    with SessionLocal() as db:
        jobs = list(db.scalars(select(Job).where(Job.last_error != "")))
        assert len(jobs) == 1 and jobs[0].state == "pending"


def test_task_permissions_completion_and_reopening(env):
    c, ids = env
    lead = make_lead(c["caller"])
    body = {"title": "Call customer", "due_at": now().isoformat(), "lead_id": lead["id"]}
    assert c["caller2"].post("/api/tasks", json=body).status_code == 404
    assert c["caller"].post("/api/tasks", json={**body, "owner_id": ids["caller2"]}).status_code == 403
    r = c["caller"].post("/api/tasks", json=body)
    assert r.status_code == 201
    task = r.json()
    assert c["caller2"].put("/api/tasks/" + task["id"], json=body).status_code == 404
    for state in ["completed", "open", "cancelled", "open"]:
        r = c["caller"].put("/api/tasks/" + task["id"], json={**body, "state": state})
        assert r.status_code == 200
        assert bool(r.json()["completed_at"]) == (state == "completed")
    c["admin"].post("/api/leads/assign", json={"lead_ids": [lead["id"]], "owner_id": ids["caller2"]})
    assert c["caller"].get("/api/tasks").json() == []
    assert c["caller"].delete("/api/tasks/" + task["id"]).status_code == 404


def test_analytics_deduplicates_linked_outcome_and_preserves_money(env):
    c, _ = env
    lead = make_lead(c["caller"])
    c["caller"].post(
        "/api/phone-calls/sync",
        json={
            "device_id": "metric-device",
            "calls": [
                {
                    "device_call_id": "1",
                    "phone": lead["phone"],
                    "direction": "outgoing",
                    "result": "answered",
                    "started_at": now().isoformat(),
                    "duration": 120,
                }
            ],
        },
    )
    call = c["caller"].get("/api/phone-calls").json()["items"][0]
    r = c["caller"].post(
        "/api/leads/" + lead["id"] + "/outcomes",
        json={
            "outcome": "converted",
            "duration": 120,
            "phone_call_id": call["id"],
            "order_value": "250.25",
            "request_id": "linked-outcome-123",
        },
    )
    assert r.status_code == 201
    c["caller"].post(
        "/api/leads/" + lead["id"] + "/outcomes",
        json={"outcome": "converted", "duration": 60, "order_value": "100.10", "request_id": "standalone-outcome-123"},
    )
    data = c["admin"].get("/api/analytics").json()
    m = data["metrics"]
    assert m["calls"] == 2 and m["talk_seconds"] == 180 and m["observed_seconds"] == 120 and m["declared_seconds"] == 60
    assert m["order_value"] == "350.35" and m["leads"] == 1 and m["converted"] == 1
    assert (
        sum(data["statuses"].values()) == m["leads"]
        and sum(data["sources"].values()) == m["leads"]
        and sum(h["calls"] for h in data["hourly"]) == 2
    )
    assert (
        c["admin"].get("/api/analytics?from_date=2026-10-02T00:00:00Z&to_date=2026-10-01T00:00:00Z").status_code == 422
    )
    assert "350.35" in c["admin"].get("/api/analytics?export=true").text
    assert c["other"].get("/api/analytics").json()["metrics"]["calls"] == 0


def test_snapshots_exclude_secrets_and_are_scoped(env):
    c, _ = env
    make_lead(c["caller"])
    r = c["admin"].post("/api/backups")
    assert r.status_code == 201, r.text
    raw = c["admin"].get("/api/backups/" + r.json()["id"])
    assert raw.status_code == 200 and raw.json()["data"]["leads"][0]["name"] == "Example Customer"
    text = raw.text
    for secret in ["password_hash", "refresh_hash", "totp_secret", "TestPassword!123"]:
        assert secret not in text
    assert c["other"].get("/api/backups/" + r.json()["id"]).status_code == 404


def test_worker_health_and_suspended_org_jobs(env):
    c, ids = env
    assert c["admin"].get("/api/health").json()["worker"] == "offline"
    tick()
    assert c["admin"].get("/api/health").json()["worker"] == "ok"
    c["admin"].post(
        "/api/automations",
        json={"name": "Add note", "trigger": "lead_created", "action": "add_note", "config": {"text": "Should wait"}},
    )
    lead = make_lead(c["caller"])
    c["owner"].patch("/api/platform/organizations/" + ids["org"], json={"active": False})
    process_organization(ids["org"])
    with SessionLocal() as db:
        assert not db.scalar(select(Note).where(Note.lead_id == lead["id"]))
