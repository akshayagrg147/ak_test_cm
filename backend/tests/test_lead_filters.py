import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from app.db import SessionLocal, now
from app.models import Lead
from conftest import make_lead


def test_every_lead_filter_combination_export_and_role_scope(env):
    clients, ids = env
    a = make_lead(clients["caller"], name="Panipat buyer A", city="Panipat", state="Haryana", source="website", stage="qualified", category="other", interests=["Sunrise Court"])
    b = make_lead(clients["caller2"], name="Panipat buyer B", phone="9810001235", city="Panipat", state="Haryana", source="broker", dnd=True)
    c = make_lead(clients["admin"], name="Delhi lost lead", phone="9810001236", city="Delhi", state="Delhi", source="website")
    d = make_lead(clients["caller"], name="Pune next callback", phone="9810001237", city="Pune", state="Maharashtra")
    clock = now()
    with SessionLocal.begin() as db:
        for lead in [a, c, d]:
            db.get(Lead, lead["id"]).created_at = clock - timedelta(days=1)
        lead_a, lead_b, lead_c, lead_d = [db.get(Lead, lead["id"]) for lead in [a, b, c, d]]
        lead_a.status, lead_a.follow_up, lead_a.last_contact = "follow-up", clock - timedelta(hours=1), clock - timedelta(hours=2)
        lead_b.created_at = clock - timedelta(days=3)
        lead_c.status, lead_c.stage, lead_c.reported_by, lead_c.lost_reason = "lost", "lost", ids["caller"], "Budget too high"
        lead_d.status, lead_d.stage = "follow-up", "qualified"
        lead_d.follow_up, lead_d.last_contact = clock + timedelta(days=1), clock - timedelta(hours=1)
    cases = [
        ({"q": "panipat"}, [a, b]),
        ({"status": "lost"}, [c]),
        ({"source": "website"}, [a, c]),
        ({"owner_id": ids["caller"]}, [a, d]),
        ({"owner_id": "unassigned"}, [c]),
        ({"city": " pAnIpAt "}, [a, b]),
        ({"state": " HARYANA "}, [a, b]),
        ({"category": "other"}, [a]),
        ({"interest": "sunrise"}, [a]),
        ({"stage": "qualified"}, [a, d]),
        ({"dnd": "true"}, [b]),
        ({"dnd": "false"}, [a, c, d]),
        ({"callback": "overdue"}, [a]),
        ({"callback": "upcoming"}, [d]),
        ({"callback": "stale"}, [b]),
        ({"reported_by": ids["caller"], "reason": "BUDGET"}, [c]),
        ({"from_date": (clock - timedelta(days=2)).isoformat(), "to_date": clock.isoformat()}, [a, c, d]),
        ({"source": "website", "owner_id": ids["caller"], "city": "PANIPAT", "state": "haryana", "status": "follow-up", "stage": "qualified", "interest": "sunrise", "dnd": "false"}, [a]),
    ]
    for filters, expected in cases:
        response = clients["admin"].get("/api/leads", params=filters)
        assert response.status_code == 200, response.text
        assert {lead["id"] for lead in response.json()["items"]} == {lead["id"] for lead in expected}, filters
        exported = clients["admin"].get("/api/leads/export", params=filters)
        assert exported.status_code == 200
        assert {row["name"] for row in csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))} == {lead["name"] for lead in expected}, filters
        assert clients["other"].get("/api/leads", params=filters).json()["total"] == 0
    assert [lead["id"] for lead in clients["caller"].get("/api/leads?city=panipat").json()["items"]] == [a["id"]]


@pytest.mark.parametrize("field", ["status", "source", "callback"])
def test_unsupported_lead_filter_is_explained_instead_of_ignored(env, field):
    clients, _ = env
    for path in ["/api/leads", "/api/leads/export"]:
        response = clients["admin"].get(path, params={field: "not-a-valid-choice"})
        assert response.status_code == 422, response.text
        assert field in response.json()["error"]["message"]


def test_calendar_range_includes_start_and_last_instant_but_not_next_day(env):
    clients, _ = env
    leads = [make_lead(clients["caller"], name=f"Boundary {i}", phone=f"981000124{i}") for i in range(3)]
    # New York's 8 March 2026 calendar day is 23 hours long.
    start = datetime(2026, 3, 8, 5, tzinfo=timezone.utc)
    end = datetime(2026, 3, 9, 4, tzinfo=timezone.utc)
    with SessionLocal.begin() as db:
        for lead, created in zip(leads, [start, end - timedelta(microseconds=1), end]):
            db.get(Lead, lead["id"]).created_at = created
    filters = {"from_date": start.isoformat(), "to_date": end.isoformat()}
    assert {lead["id"] for lead in clients["admin"].get("/api/leads", params=filters).json()["items"]} == {lead["id"] for lead in leads[:2]}
