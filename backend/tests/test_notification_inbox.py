from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app import notification_inbox
from app.db import SessionLocal, now
from app.models import Definition, FieldHandoff, Lead, Organization, Task
from conftest import make_lead
from test_field_work import create, field_env as field_env


def overdue(client, phone="+919812340001", **kwargs):
    lead = make_lead(client, phone=phone, **kwargs)
    with SessionLocal.begin() as db:
        db.get(Lead, lead["id"]).follow_up = now() - timedelta(minutes=20)
    return lead


def test_inbox_empty_validates_paging_and_keeps_legacy_shape(env):
    c, _ = env
    response = c["caller"].get("/api/notifications/inbox")
    assert response.status_code == 200
    data = response.json()
    assert data["counts"] == {"callbacks": 0, "other": 0, "all": 0}
    assert data["items"] == [] and data["total"] == 0 and data["page"] == data["pages"] == 1
    assert data["timezone"] == "Asia/Kolkata"
    assert isinstance(c["caller"].get("/api/notifications").json(), list)
    assert c["owner"].get("/api/notifications/inbox").status_code == 403
    for params in [{"page": 0}, {"page_size": 0}, {"page_size": 51}, {"category": "wrong"}]:
        assert c["admin"].get("/api/notifications/inbox", params=params).status_code == 422


def test_inbox_excludes_future_closed_dnd_deleted_and_does_not_mislabel_future_callbacks(env, monkeypatch):
    c, ids = env
    stamp = now()
    monkeypatch.setattr(notification_inbox, "now", lambda: stamp)
    leads = [make_lead(c["caller"], name=f"Notification {i}", phone=f"+9198123410{i:02}") for i in range(13)]
    with SessionLocal.begin() as db:
        db.add(
            Definition(
                org_id=ids["org"],
                kind="stage",
                key="inactive_closed",
                label="Closed",
                active=False,
                config={"closed": True},
            )
        )
        for index, row in enumerate(leads):
            item = db.get(Lead, row["id"])
            item.follow_up = stamp - timedelta(hours=1)
            item.created_at = stamp - timedelta(days=4)
            if index == 1:
                item.follow_up = stamp
            if index == 2:
                item.follow_up = stamp + timedelta(seconds=1)
            if index == 3:
                item.dnd = True
            if index == 4:
                item.status = "converted"
            if index == 5:
                item.status = "lost"
            if index == 6:
                item.stage = "won"
            if index == 7:
                item.stage = "lost"
            if index == 8:
                item.stage = "inactive_closed"
            if index == 9:
                item.deleted = True
            if index == 10:
                item.follow_up = None
            if index == 11:
                item.follow_up, item.last_contact = None, stamp
            if index == 12:
                item.follow_up, item.created_at = None, stamp
    data = c["caller"].get("/api/notifications/inbox").json()
    assert data["counts"] == {"callbacks": 2, "other": 1, "all": 3}
    assert [row["lead_id"] for row in data["items"]] == [leads[0]["id"], leads[1]["id"], leads[10]["id"]]
    assert data["items"][2]["title"] == "First contact needed"
    callbacks = c["caller"].get("/api/notifications/inbox?category=callbacks").json()
    assert callbacks["total"] == 2 and all(row["kind"] == "callback" for row in callbacks["items"])


def test_viewing_or_syncing_a_call_does_not_dismiss_callback_but_result_or_reschedule_does(env):
    c, _ = env
    lead = overdue(c["caller"])
    path = "/api/notifications/inbox?category=callbacks"
    first = c["caller"].get(path).json()
    assert first["counts"]["callbacks"] == c["caller"].get(path).json()["counts"]["callbacks"] == 1
    assert (
        c["caller"]
        .post(
            "/api/phone-calls/sync",
            json={
                "device_id": "notification-test",
                "calls": [
                    {
                        "device_call_id": "1",
                        "phone": lead["phone"],
                        "direction": "outgoing",
                        "result": "answered",
                        "started_at": now().isoformat(),
                        "duration": 60,
                    }
                ],
            },
        )
        .status_code
        == 200
    )
    assert c["caller"].get(path).json()["total"] == 1
    response = c["caller"].post(
        f"/api/leads/{lead['id']}/outcomes",
        json={"outcome": "follow-up", "follow_up": (now() + timedelta(days=1)).isoformat(), "request_id": str(uuid4())},
    )
    assert response.status_code == 201
    assert c["caller"].get(path).json()["total"] == 0
    with SessionLocal.begin() as db:
        db.get(Lead, lead["id"]).follow_up = now() - timedelta(minutes=1)
    assert c["caller"].get(path).json()["total"] == 1
    assert (
        c["caller"]
        .post(f"/api/leads/{lead['id']}/outcomes", json={"outcome": "converted", "request_id": str(uuid4())})
        .status_code
        == 201
    )
    assert c["caller"].get(path).json()["total"] == 0


def test_inbox_counts_and_links_respect_company_and_current_assignment(env):
    c, ids = env
    own = overdue(c["caller"], name="My overdue client")
    overdue(c["caller2"], phone="+919812340002", name="Colleague private client")
    overdue(c["other"], phone="+919812340003", name="Other company private client")
    assert c["admin"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 2
    assert c["manager"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 2
    data = c["caller"].get("/api/notifications/inbox").json()
    assert data["counts"]["callbacks"] == 1
    assert "Colleague private" not in str(data) and "Other company" not in str(data)
    assert data["items"][0]["url"] == "/app/leads/" + own["id"]
    assert (
        c["admin"].post("/api/leads/assign", json={"lead_ids": [own["id"]], "owner_id": ids["caller2"]}).status_code
        == 200
    )
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 0
    assert c["caller2"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 2


def test_open_callback_tasks_are_counted_and_completion_or_reschedule_removes_them(env):
    c, _ = env
    payload = {
        "title": "Call about the shortlist",
        "kind": "callback",
        "due_at": (now() - timedelta(minutes=5)).isoformat(),
    }
    response = c["caller"].post("/api/tasks", json=payload)
    assert response.status_code == 201
    task = response.json()
    assert c["caller2"].post("/api/tasks", json=payload).status_code == 201
    assert (
        c["caller"].post("/api/tasks", json={**payload, "kind": "task", "title": "Prepare paperwork"}).status_code
        == 201
    )
    future = (now() + timedelta(hours=1)).isoformat()
    assert (
        c["caller"].post("/api/tasks", json={**payload, "due_at": future, "title": "Future callback"}).status_code
        == 201
    )
    data = c["caller"].get("/api/notifications/inbox").json()
    assert data["counts"] == {"callbacks": 1, "other": 2, "all": 3}
    assert data["items"][0]["title"] == "Callback task overdue" and data["items"][0]["url"] == "/app/tasks"
    assert c["caller"].put("/api/tasks/" + task["id"], json={**payload, "state": "completed"}).status_code == 200
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 0
    assert (
        c["caller"].put("/api/tasks/" + task["id"], json={**payload, "state": "open", "due_at": future}).status_code
        == 200
    )
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 0


def test_callback_tasks_for_closed_or_dnd_clients_and_reassigned_private_tasks_are_hidden(env):
    c, ids = env
    lead = make_lead(c["caller"])
    assert (
        c["caller"]
        .post(
            "/api/tasks",
            json={
                "title": "Callback the client",
                "kind": "callback",
                "lead_id": lead["id"],
                "due_at": (now() - timedelta(minutes=1)).isoformat(),
            },
        )
        .status_code
        == 201
    )
    with SessionLocal.begin() as db:
        db.get(Lead, lead["id"]).dnd = True
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 0
    with SessionLocal.begin() as db:
        item = db.get(Lead, lead["id"])
        item.dnd, item.stage = False, "won"
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 0
    with SessionLocal.begin() as db:
        item = db.get(Lead, lead["id"])
        item.stage, item.owner_id = "new", ids["caller2"]
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["all"] == 0


def test_pagination_keeps_exact_count_beyond_old_limit_and_clamps_after_resolution(env):
    c, ids = env
    stamp = now()
    with SessionLocal.begin() as db:
        db.add_all(
            [
                Lead(
                    org_id=ids["org"],
                    owner_id=ids["caller"],
                    name=f"Callback {index:03}",
                    phone=f"+91981235{index:04}",
                    follow_up=stamp - timedelta(minutes=130 - index),
                )
                for index in range(105)
            ]
        )
    all_ids = []
    for page in range(1, 10):
        data = c["caller"].get("/api/notifications/inbox", params={"category": "callbacks", "page": page}).json()
        assert data["total"] == data["counts"]["callbacks"] == 105 and data["pages"] == 9
        assert data["page"] == page
        all_ids.extend(row["id"] for row in data["items"])
    assert len(all_ids) == len(set(all_ids)) == 105
    assert c["caller"].get("/api/notifications/inbox?page=99999").json()["page"] == 9
    with SessionLocal.begin() as db:
        for lead in db.scalars(select(Lead).where(Lead.org_id == ids["org"])):
            lead.follow_up = stamp + timedelta(hours=1)
    empty = c["caller"].get("/api/notifications/inbox?page=9").json()
    assert empty["page"] == empty["pages"] == 1 and empty["items"] == [] and empty["counts"]["all"] == 0


def test_inbox_shared_field_access_and_managed_callback_links_follow_current_handoff(field_env):
    c, ids, prop = field_env
    lead, item, _ = create(c, ids, prop)
    with SessionLocal.begin() as db:
        db.get(Lead, lead["id"]).follow_up = now() - timedelta(hours=1)
        task = Task(
            org_id=ids["org"],
            lead_id=lead["id"],
            owner_id=ids["field"],
            creator_id=ids["caller"],
            title="Discuss the visit feedback",
            kind="callback",
            due_at=now() - timedelta(minutes=1),
        )
        db.add(task)
        db.flush()
        db.get(FieldHandoff, item["id"]).task_id = task.id
    data = c["field"].get("/api/notifications/inbox").json()
    assert data["counts"]["callbacks"] == 2
    assert any(row["title"] == "Accept client handoff" for row in data["items"])
    managed = next(row for row in data["items"] if row["title"] == "Field follow-up overdue")
    assert managed["url"] == "/app/leads/" + lead["id"]
    assert c["field2"].get("/api/notifications/inbox").json()["counts"]["all"] == 0
    response = c["admin"].patch(
        "/api/field-work/" + item["id"],
        json={
            "version": item["version"],
            "action": "reassign",
            "executive_id": ids["field2"],
            "feedback": "Another executive takes over",
        },
    )
    assert response.status_code == 200
    assert c["field"].get("/api/notifications/inbox").json()["counts"]["all"] == 0
    # Existing field reassignment transfers the open managed callback task too.
    assert c["field2"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 2
    assert c["caller"].get("/api/notifications/inbox").json()["counts"]["callbacks"] == 1


def test_inbox_uses_workplace_timezone_metadata_with_exact_utc_deadline(env, monkeypatch):
    c, ids = env
    stamp = now()
    monkeypatch.setattr(notification_inbox, "now", lambda: stamp)
    lead = overdue(c["caller"])
    with SessionLocal.begin() as db:
        item = db.get(Lead, lead["id"])
        item.follow_up = stamp
        org = db.get(Organization, ids["org"])
        org.settings = {**org.settings, "workplace": {**org.settings["workplace"], "timezone": "America/New_York"}}
    data = c["caller"].get("/api/notifications/inbox").json()
    assert data["timezone"] == "America/New_York" and data["counts"]["callbacks"] == 1
    assert data["items"][0]["due_at"] == stamp.isoformat()
