from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4

import pytest

from app import reports
from app.db import SessionLocal, now
from app.models import Definition, Lead, ManualCall
from conftest import make_lead
from test_field_work import create
from test_field_work import field_env as field_env


@pytest.mark.parametrize("days", [1, 7, 30])
def test_empty_dashboard_has_real_zeroes_and_complete_buckets(env, days):
    c, _ = env
    response = c["admin"].get(f"/api/dashboard?days={days}")
    assert response.status_code == 200
    data = response.json()
    assert data["period_days"] == days and data["timezone"] == "Asia/Kolkata"
    assert data["metrics"]["leads"] == data["metrics"]["calls"] == data["metrics"]["actionable_overdue"] == 0
    assert sum(r["calls"] + r["leads"] for r in data["trend"]) == 0
    assert len(data["trend"]) == (
        datetime.fromisoformat(data["to_date"]).astimezone(ZoneInfo("Asia/Kolkata")).hour + 1 if days == 1 else days
    )
    assert data["priority"] == [] and data["priority_total"] == 0


def test_dashboard_counts_device_calls_once_and_keeps_manual_results_separate(env):
    c, ids = env
    lead = make_lead(c["caller"])
    synced = c["caller"].post(
        "/api/phone-calls/sync",
        json={
            "device_id": "dashboard-qa",
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
    assert synced.status_code == 200
    call = c["caller"].get("/api/phone-calls").json()["items"][0]
    for extra in [{"phone_call_id": call["id"]}, {}]:
        response = c["caller"].post(
            f"/api/leads/{lead['id']}/outcomes",
            json={
                "outcome": "follow-up",
                "duration": 60,
                "follow_up": (now() + timedelta(days=1)).isoformat(),
                "request_id": str(uuid4()),
                **extra,
            },
        )
        assert response.status_code == 201, response.text
    data = c["admin"].get("/api/dashboard?days=7").json()
    assert (
        data["metrics"]["calls"]
        == sum(day["calls"] for day in data["trend"])
        == sum(data["call_results"].values())
        == 2
    )
    assert data["metrics"]["talk_seconds"] == 180
    assert data["call_results"] == {"answered": 1, "manual": 1}
    assert (
        sum(day["leads"] for day in data["trend"])
        == sum(stage["count"] for stage in data["pipeline"])
        == data["metrics"]["leads"]
        == 1
    )
    assert c["caller"].get("/api/dashboard?days=7").json()["leaderboard"][0]["user_id"] == ids["caller"]


def test_dashboard_uses_workplace_midnight_and_keeps_calls_outside_the_period_out(env, monkeypatch):
    c, ids = env
    zone = ZoneInfo("Asia/Kolkata")
    stamp = datetime(2026, 10, 26, 0, 30, tzinfo=zone)
    monkeypatch.setattr(reports, "now", lambda: stamp)
    before = make_lead(c["caller"], phone="+919810009801")
    after = make_lead(c["caller"], phone="+919810009802")
    midnight = stamp.replace(minute=0)
    with SessionLocal.begin() as db:
        db.get(Lead, before["id"]).created_at = midnight - timedelta(seconds=1)
        db.get(Lead, after["id"]).created_at = midnight
        for index, instant in enumerate([midnight - timedelta(seconds=1), midnight, stamp + timedelta(seconds=1)]):
            db.add(
                ManualCall(
                    org_id=ids["org"],
                    lead_id=after["id"],
                    user_id=ids["caller"],
                    outcome="follow-up",
                    duration=10,
                    created_at=instant,
                    order_value=0,
                    request_id=f"midnight-{index}",
                )
            )
    today = c["caller"].get("/api/dashboard?days=1").json()
    assert today["metrics"]["leads"] == today["metrics"]["calls"] == 1
    assert today["trend"] == [{"key": "0", "label": "00:00", "leads": 1, "calls": 1}]
    week = c["caller"].get("/api/dashboard?days=7").json()
    assert week["metrics"]["leads"] == week["metrics"]["calls"] == 2
    assert [row["calls"] for row in week["trend"]][-2:] == [1, 1]
    assert len(week["trend"]) == 7


def test_dashboard_respects_tenant_owner_and_role_scopes(env):
    c, ids = env
    first = make_lead(c["caller"], name="Caller one private", phone="+919810009811")
    make_lead(c["caller2"], name="Caller two private", phone="+919810009812")
    make_lead(c["other"], name="Other company private", phone="+919810009813")
    assert c["admin"].get("/api/dashboard").json()["metrics"]["visible_leads"] == 2
    own = c["caller"].get("/api/dashboard").json()
    assert own["metrics"]["visible_leads"] == 1 and own["priority"][0]["lead"]["id"] == first["id"]
    assert "Caller two private" not in str(own) and "Other company private" not in str(own)
    assert c["admin"].get("/api/dashboard", params={"owner_id": ids["caller2"]}).json()["metrics"]["visible_leads"] == 1
    assert (
        c["caller"].get("/api/dashboard", params={"owner_id": ids["caller2"]}).json()["metrics"]["visible_leads"] == 0
    )
    assert c["admin"].get("/api/dashboard", params={"owner_id": ids["other"]}).json()["metrics"]["visible_leads"] == 0
    assert c["owner"].get("/api/dashboard").status_code == 403
    for days in [0, -1, 8, 31, 1000, "bad"]:
        assert c["admin"].get("/api/dashboard", params={"days": days}).status_code == 422


def test_dashboard_priority_excludes_closed_dnd_archived_and_sorts_real_due_work(env):
    c, ids = env
    leads = [make_lead(c["caller"], name=f"Priority {i}", phone=f"+9198100099{i:02}") for i in range(14)]
    with SessionLocal.begin() as db:
        for index, lead in enumerate(leads):
            item = db.get(Lead, lead["id"])
            item.follow_up = now() - timedelta(hours=index + 1)
        db.get(Lead, leads[0]["id"]).dnd = True
        db.get(Lead, leads[1]["id"]).status = "converted"
        db.get(Lead, leads[2]["id"]).status = "lost"
        db.get(Lead, leads[3]["id"]).deleted = True
        db.get(Lead, leads[4]["id"]).stage = "won"
        db.get(Lead, leads[5]["id"]).stage = "lost"
        # Historical/custom closed stages stay closed even if deactivated, and
        # importing a stage without a matching status must not prompt a call.
        db.add(
            Definition(
                org_id=ids["org"],
                kind="stage",
                key="custom_closed",
                label="Closed enquiry",
                config={"closed": True},
                active=False,
            )
        )
        db.get(Lead, leads[6]["id"]).stage = "custom_closed"
    data = c["caller"].get("/api/dashboard").json()
    assert data["metrics"]["visible_leads"] == 13 and data["metrics"]["actionable_overdue"] == 7
    assert data["priority_total"] == 7 and len(data["priority"]) == 6
    assert [item["lead"]["id"] for item in data["priority"]] == [lead["id"] for lead in leads[:7:-1]]


def test_dashboard_shared_field_scope_is_revoked_on_reassignment(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    assert c["field"].get("/api/dashboard").json()["metrics"]["visible_leads"] == 1
    assert c["field2"].get("/api/dashboard").json()["metrics"]["visible_leads"] == 0
    reassigned = c["admin"].patch(
        "/api/field-work/" + item["id"],
        json={
            "version": item["version"],
            "action": "reassign",
            "executive_id": ids["field2"],
            "feedback": "Change responsible executive",
        },
    )
    assert reassigned.status_code == 200
    assert c["field"].get("/api/dashboard").json()["metrics"]["visible_leads"] == 0
    assert c["field2"].get("/api/dashboard").json()["metrics"]["visible_leads"] == 1
    assert c["caller"].get("/api/dashboard").json()["metrics"]["visible_leads"] == 1
