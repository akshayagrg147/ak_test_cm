import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app.db import SessionLocal, uid
from app.models import Attendance, Lead, ManualCall, Organization, PayProfile, PhoneCall, TimeEntry
from conftest import make_lead


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def office(ids, start="2026-10-05T03:30:00Z", end="2026-10-05T11:30:00Z", state="approved"):
    start, end = stamp(start), stamp(end)
    with SessionLocal.begin() as db:
        item = Attendance(
            org_id=ids["org"],
            user_id=ids["caller"],
            day=start.date(),
            checked_in=start,
            checked_out=end,
            cutoff=end,
            location={},
        )
        db.add(item)
        db.flush()
        entry = TimeEntry(
            org_id=ids["org"],
            user_id=ids["caller"],
            day=start.date(),
            hours=Decimal(str((end - start).total_seconds())) / 3600,
            category="other",
            description="Synthetic office attendance",
            source="attendance",
            source_id=item.id,
            state=state,
        )
        db.add(entry)
        db.flush()
        return entry.id


def call(ids, lead, start="2026-10-05T05:30:00Z", duration=7200, **extra):
    with SessionLocal.begin() as db:
        item = PhoneCall(
            org_id=ids["org"],
            user_id=ids["caller"],
            lead_id=lead["id"],
            device_id="pay-device",
            device_call_id=uid(),
            phone=lead["phone"],
            started_at=stamp(start),
            duration=duration,
            direction="outgoing",
            result="answered",
            **extra,
        )
        db.add(item)
        db.flush()
        return item.id


def configure(admin, ids, **extra):
    response = admin.put(
        "/api/payroll/profiles/" + ids["caller"],
        json={
            "hourly_rate": "100",
            "daily_target": "8",
            "pay_basis": "office_calls",
            "call_hourly_rate": "150",
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def result(admin, ids, month="2026-10"):
    response = admin.get("/api/payroll", params={"month": month})
    assert response.status_code == 200, response.text
    return next(row for row in response.json()["items"] if row["user_id"] == ids["caller"])


def test_eight_office_two_call_hours_pay_six_plus_two_and_do_not_double_count(env):
    c, ids = env
    lead = make_lead(c["caller"])
    office(ids)
    first = call(ids, lead)
    # The same interval from another installation and a linked outcome add no pay time.
    call(ids, lead)
    with SessionLocal.begin() as db:
        db.add(
            ManualCall(
                org_id=ids["org"],
                user_id=ids["caller"],
                lead_id=lead["id"],
                duration=8500,
                outcome="follow-up",
                phone_call_id=first,
                request_id=uid(),
            )
        )
    configure(c["admin"], ids)
    row = result(c["admin"], ids)
    assert row["office_hours"] == "8.0000" and row["approved_office_hours"] == "8.0000"
    assert row["call_hours"] == "2.0000" and row["non_call_office_hours"] == "6.0000"
    assert row["base_pay"] == "600.00" and row["call_pay"] == "300.00" and row["estimated_pay"] == "900.00"
    assert row["answered_call_records"] == 2 and row["declared_call_seconds"] == "0"
    assert row["calls_during_office_seconds"] == "7200.0" and row["calls_outside_office_seconds"] == "0.0"
    exported = c["admin"].get("/api/payroll/export?month=2026-10")
    exported_row = next(
        item for item in csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))) if item["name"] == row["name"]
    )
    assert (
        exported_row["base_pay"] == row["base_pay"]
        and exported_row["call_pay"] == row["call_pay"]
        and exported_row["estimated_pay"] == row["estimated_pay"]
    )
    with SessionLocal.begin() as db:
        customer = db.get(Lead, lead["id"])
        customer.owner_id = ids["caller2"]
        customer.deleted = True
    assert result(c["admin"], ids)["estimated_pay"] == "900.00"


def test_calls_outside_office_are_paid_without_subtracting_unrelated_office_time(env):
    c, ids = env
    lead = make_lead(c["caller"])
    office(ids)
    call(ids, lead, start="2026-10-05T02:30:00Z", duration=7200)
    call(ids, lead, start="2026-10-05T10:30:00Z", duration=7200)
    configure(c["admin"], ids)
    row = result(c["admin"], ids)
    assert row["call_hours"] == "4.0000" and row["non_call_office_hours"] == "6.0000"
    assert row["calls_outside_office_seconds"] == "7200.0"
    assert row["estimated_pay"] == "1200.00"


@pytest.mark.parametrize("state", ["pending", "rejected"])
def test_only_approved_office_is_paid_and_manual_claims_do_not_create_office_or_call_time(env, state):
    c, ids = env
    lead = make_lead(c["caller"])
    office(ids, state=state)
    call(ids, lead)
    with SessionLocal.begin() as db:
        db.add(
            TimeEntry(
                org_id=ids["org"],
                user_id=ids["caller"],
                day=date(2026, 10, 5),
                hours=8,
                category="calling",
                description="Manual work claim",
                source="manual",
                state="approved",
            )
        )
        db.add(
            ManualCall(
                org_id=ids["org"],
                user_id=ids["caller"],
                lead_id=lead["id"],
                duration=36000,
                outcome="converted",
                request_id=uid(),
                created_at=stamp("2026-10-05T09:30:00Z"),
            )
        )
    configure(c["admin"], ids)
    row = result(c["admin"], ids)
    assert row["office_hours"] == "8.0000" and row["approved_office_hours"] == "0.0000"
    assert row["base_pay"] == "0.00" and row["call_pay"] == "300.00" and row["approved_hours"] == "8.00"
    assert row["declared_call_seconds"] == "36000"
    configure(c["admin"], ids, pay_basis="work")
    row = result(c["admin"], ids)
    assert row["estimated_pay"] == "800.00" and row["call_pay"] == "0.00"


def test_only_answered_elapsed_synced_time_counts_and_recording_is_not_required(env, monkeypatch):
    c, ids = env
    lead = make_lead(c["caller"])
    as_of = stamp("2026-10-05T10:00:00Z")
    monkeypatch.setattr("app.workforce.now", lambda: as_of)
    call(ids, lead, start="2026-10-05T09:59:55Z", duration=100, recording_state="unavailable")
    call(ids, lead, start="2026-10-05T10:00:01Z", duration=3600)
    with SessionLocal.begin() as db:
        for status in ["missed", "rejected", "unknown"]:
            db.add(
                PhoneCall(
                    org_id=ids["org"],
                    user_id=ids["caller"],
                    lead_id=lead["id"],
                    phone=lead["phone"],
                    device_id="ignored",
                    device_call_id=uid(),
                    direction="incoming",
                    result=status,
                    duration=3600,
                    started_at=as_of - timedelta(hours=2),
                )
            )
    configure(c["admin"], ids)
    row = result(c["admin"], ids)
    assert row["call_seconds"] == "5.0" and row["answered_call_records"] == 1
    assert row["estimated_pay"] == "0.21"
    assert c["other"].get("/api/payroll?month=2026-10").json()["items"][0]["call_seconds"] == "0"


def test_month_boundaries_use_workplace_timezone_and_split_crossing_calls(env, monkeypatch):
    c, ids = env
    lead = make_lead(c["caller"])
    monkeypatch.setattr("app.workforce.now", lambda: stamp("2026-11-02T00:00:00Z"))
    call(ids, lead, start="2026-09-30T18:00:00Z", duration=3600)
    call(ids, lead, start="2026-10-31T18:00:00Z", duration=3600)
    configure(c["admin"], ids)
    row = result(c["admin"], ids)
    assert row["call_hours"] == "1.0000" and row["estimated_pay"] == "150.00"
    assert [(day["day"], day["call_seconds"]) for day in row["daily"]] == [
        ("2026-10-01", "1800.0"),
        ("2026-10-31", "1800.0"),
    ]


@pytest.mark.parametrize(
    "start,end,month,hours",
    [
        ("2026-03-08T05:00:00Z", "2026-03-09T04:00:00Z", "2026-03", 23),
        ("2026-11-01T04:00:00Z", "2026-11-02T05:00:00Z", "2026-11", 25),
    ],
)
def test_office_uses_real_elapsed_time_on_short_and_long_daylight_saving_days(
    env, monkeypatch, start, end, month, hours
):
    c, ids = env
    lead = make_lead(c["caller"])
    with SessionLocal.begin() as db:
        org = db.get(Organization, ids["org"])
        org.settings = {**org.settings, "workplace": {**org.settings["workplace"], "timezone": "America/New_York"}}
    monkeypatch.setattr("app.workforce.now", lambda: stamp(end) + timedelta(days=1))
    office(ids, start, end)
    call(ids, lead, start=start, duration=7200)
    configure(c["admin"], ids)
    row = result(c["admin"], ids, month)
    assert Decimal(row["approved_office_hours"]) == hours
    assert Decimal(row["base_paid_hours"]) == hours - 2
    assert Decimal(row["estimated_pay"]) == (hours - 2) * 100 + 300


def test_separate_money_components_round_once_and_reconcile(env):
    c, ids = env
    lead = make_lead(c["caller"])
    office(ids, start="2026-10-05T03:30:00Z", end="2026-10-05T03:30:02Z")
    call(ids, lead, start="2026-10-05T03:30:00Z", duration=1)
    configure(c["admin"], ids, hourly_rate="100.01", call_hourly_rate="200.02")
    row = result(c["admin"], ids)
    assert row["base_pay"] == "0.03" and row["call_pay"] == "0.06" and row["estimated_pay"] == "0.09"


def test_pay_configuration_validation_preserves_legacy_updates_and_admin_only_scope(env):
    c, ids = env
    configured = configure(c["admin"], ids)
    old_payload = {"hourly_rate": "120", "daily_target": "8"}
    assert (
        c["admin"].put("/api/payroll/profiles/" + ids["caller"], json=old_payload).json()["call_hourly_rate"]
        == "150.00"
    )
    assert result(c["admin"], ids)["pay_basis"] == "office_calls"
    for changes in [
        {"pay_basis": "wrong"},
        {"call_hourly_rate": 0},
        {"call_hourly_rate": -1},
        {"call_hourly_rate": "NaN"},
        {"call_hourly_rate": "1.123"},
    ]:
        assert (
            c["admin"].put("/api/payroll/profiles/" + ids["caller"], json={**old_payload, **changes}).status_code == 422
        )
    for role in ["caller", "manager"]:
        assert c[role].get("/api/payroll?month=2026-10").status_code == 403
        assert c[role].get("/api/payroll/export?month=2026-10").status_code == 403
        assert c[role].put("/api/payroll/profiles/" + ids["caller"], json=old_payload).status_code == 403
        assert "call_hourly_rate" not in c[role].get("/api/directory").text
    assert c["other"].put("/api/payroll/profiles/" + ids["caller"], json=old_payload).status_code == 404
    assert configured["pay_basis"] == "office_calls"
    for month in ["0001-01", "9999-12"]:
        assert c["admin"].get("/api/payroll", params={"month": month}).status_code == 422
    future = result(c["admin"], ids, "2099-12")
    assert future["call_hours"] == "0.0000" and future["estimated_pay"] == "0.00"


def test_migration_preserves_existing_rate_and_approved_work_method(env):
    _, ids = env
    config = Config("alembic.ini")
    command.downgrade(config, "0005")
    with SessionLocal.begin() as db:
        db.execute(
            text(
                "INSERT INTO pay_profiles (id,org_id,user_id,created_at,hourly_rate,daily_target) VALUES (:id,:org,:user,:at,125.25,8)"
            ),
            {"id": uid(), "org": ids["org"], "user": ids["caller"], "at": datetime.now(timezone.utc)},
        )
    command.upgrade(config, "head")
    with SessionLocal() as db:
        profile = db.scalar(select(PayProfile).where(PayProfile.user_id == ids["caller"]))
        assert (
            profile.hourly_rate == Decimal("125.25") and profile.pay_basis == "work" and profile.call_hourly_rate == 0
        )
    command.downgrade(config, "0005")
    command.upgrade(config, "head")


def test_open_attendance_is_visible_but_unpaid_until_closed_and_approved(env, monkeypatch):
    c, ids = env
    lead = make_lead(c["caller"])
    as_of = stamp("2026-10-05T10:00:00Z")
    monkeypatch.setattr("app.workforce.now", lambda: as_of)
    with SessionLocal.begin() as db:
        db.add(
            Attendance(
                org_id=ids["org"],
                user_id=ids["caller"],
                day=date(2026, 10, 5),
                checked_in=as_of - timedelta(hours=2),
                cutoff=as_of + timedelta(hours=4),
                location={},
            )
        )
    call(ids, lead, start="2026-10-05T08:00:00Z", duration=3600)
    configure(c["admin"], ids)
    row = result(c["admin"], ids)
    assert row["office_hours"] == "2.0000" and row["open_attendance"] == 1
    assert row["pending_office_hours"] == "2.0000" and row["approved_office_hours"] == "0.0000"
    assert row["base_pay"] == "0.00" and row["estimated_pay"] == "150.00"


def test_android_sync_retry_and_duration_updates_recalculate_salary_once(env, monkeypatch):
    c, ids = env
    lead = make_lead(c["caller"])
    office(ids)
    clock = stamp("2026-10-06T12:00:00Z")
    monkeypatch.setattr("app.workforce.now", lambda: clock)
    monkeypatch.setattr("app.phone_calls.now", lambda: clock)
    configure(c["admin"], ids)
    payload = {
        "device_id": "salary-sync",
        "calls": [
            {
                "device_call_id": "salary-1",
                "phone": lead["phone"],
                "started_at": "2026-10-05T05:30:00Z",
                "duration": 1800,
                "direction": "outgoing",
                "result": "answered",
            }
        ],
    }
    assert c["caller"].post("/api/phone-calls/sync", json=payload).json()["created"] == 1
    assert result(c["admin"], ids)["estimated_pay"] == "825.00"
    payload["calls"][0]["duration"] = 7200
    assert c["caller"].post("/api/phone-calls/sync", json=payload).json()["updated"] == 1
    assert c["caller"].post("/api/phone-calls/sync", json=payload).json()["created"] == 0
    row = result(c["admin"], ids)
    assert row["answered_call_records"] == 1 and row["estimated_pay"] == "900.00"
