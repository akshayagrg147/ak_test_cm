"""Website, Google Ads and hosted-form lead capture with merging, auto-assignment and speed-to-lead."""

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal, now
from app.main import app
from app.models import Assignment, Lead, Provenance, SyncRun


def public():
    return TestClient(app)


def browser():
    client = TestClient(app)
    client.headers.update({"X-Requested-With": "TalkoCRM"})
    return client


def leads_named(org_id, name):
    with SessionLocal() as db:
        return list(db.scalars(select(Lead).where(Lead.org_id == org_id, Lead.name == name)))


def test_settings_are_admin_only_and_keys_are_shown_once(env):
    c, ids = env
    for role in ["manager", "caller", "owner"]:
        assert c[role].get("/api/lead-capture").status_code == 403
        assert c[role].post("/api/lead-capture/website/key").status_code == 403
    data = c["admin"].get("/api/lead-capture").json()
    assert data["form"]["enabled"] is False and data["auto_assign"] is False and data["telecallers"] == 2
    assert {ch["channel"]: ch["configured"] for ch in data["channels"]} == {"website": False, "google-ads": False}
    assert data["channels"][0]["endpoint"].endswith(f"/api/capture/{ids['org']}/website")
    generated = c["admin"].post("/api/lead-capture/website/key").json()
    assert len(generated["key"]) >= 40
    again = c["admin"].get("/api/lead-capture").json()
    assert "key" not in again and generated["key"] not in str(again)
    assert again["channels"][0]["enabled"] is True
    assert c["admin"].post("/api/lead-capture/unknown/key").status_code == 422
    revoked = c["admin"].delete("/api/lead-capture/website/key").json()
    assert revoked["channels"][0]["enabled"] is False
    assert (
        public()
        .post(
            f"/api/capture/{ids['org']}/website",
            headers={"X-Webhook-Token": generated["key"]},
            json={"name": "After Revoke", "phone": "+919811100001"},
        )
        .status_code
        == 401
    )


def test_website_webhook_creates_merges_and_deduplicates(env):
    c, ids = env
    key = c["admin"].post("/api/lead-capture/website/key").json()["key"]
    url = f"/api/capture/{ids['org']}/website"
    assert public().post(url, json={"name": "No Token", "phone": "+919811100002"}).status_code == 401
    assert (
        public()
        .post(url, headers={"X-Webhook-Token": "wrong" * 10}, json={"name": "Bad", "phone": "+919811100002"})
        .status_code
        == 401
    )
    other_org = public().post(
        f"/api/capture/{ids['other_org']}/website",
        headers={"X-Webhook-Token": key},
        json={"name": "Cross Org", "phone": "+919811100002"},
    )
    assert other_org.status_code == 401
    payload = {
        "id": "site-1",
        "Full_Name": "Riya Sharma",
        "Mobile": "98111 00003",
        "Email": "riya@example.com",
        "City": "Pune",
        "Budget": "80L",
        "Project": "Lake View",
        "Message": "Need a 2BHK",
        "utm_campaign": "diwali",
    }
    first = public().post(url, headers={"X-Webhook-Token": key}, json=payload)
    assert first.status_code == 200, first.text
    assert first.json() == {"imported": 1, "merged": 0, "duplicates": 0, "invalid": 0}
    [lead] = leads_named(ids["org"], "Riya Sharma")
    assert lead.source == "website" and lead.phone == "+919811100003" and lead.city == "Pune"
    assert lead.enquiry_at is not None and lead.owner_id is None
    for text in ["Enquiry via Website integration", "Email: riya@example.com", "Budget: 80L", "utm_campaign: diwali"]:
        assert text in lead.notes
    repeat = public().post(url, headers={"X-Webhook-Token": key}, json=payload).json()
    assert repeat["duplicates"] == 1 and repeat["imported"] == 0
    batch = (
        public()
        .post(
            url,
            headers={"X-Webhook-Token": key},
            json=[
                {"id": "site-2", "name": "Riya S", "phone": "+919811100003", "message": "Also a villa"},
                {"name": "X", "phone": "+919811100004"},
                {"name": "Bad Phone", "phone": "12"},
            ],
        )
        .json()
    )
    assert batch == {"imported": 0, "merged": 1, "duplicates": 0, "invalid": 2}
    [lead] = leads_named(ids["org"], "Riya Sharma")
    assert lead.notes.count("Enquiry via Website integration") == 2 and "Also a villa" in lead.notes
    assert public().post(url, headers={"X-Webhook-Token": key}, content=b"not json").status_code == 422
    assert public().post(url, headers={"X-Webhook-Token": key}, json=[{}] * 101).status_code == 422
    runs = c["admin"].get("/api/lead-capture").json()["recent"]
    assert runs[0]["channel"] == "website" and runs[0]["invalid"] == 2


def test_auto_assign_round_robins_captured_leads_to_active_telecallers(env):
    c, ids = env
    key = c["admin"].post("/api/lead-capture/website/key").json()["key"]
    url = f"/api/capture/{ids['org']}/website"
    public().post(url, headers={"X-Webhook-Token": key}, json={"name": "Manual Pick", "phone": "+919811100010"})
    assert c["admin"].put("/api/lead-capture", json={"auto_assign": True}).json()["auto_assign"] is True
    for index in range(3):
        public().post(
            url, headers={"X-Webhook-Token": key}, json={"name": f"Auto {index}", "phone": f"+91981110002{index}"}
        )
    owners = [leads_named(ids["org"], f"Auto {i}")[0].owner_id for i in range(3)]
    assert set(owners) == {ids["caller"], ids["caller2"]} and owners[0] == owners[2] != owners[1]
    assert leads_named(ids["org"], "Manual Pick")[0].owner_id is None
    with SessionLocal() as db:
        assert db.scalar(select(Assignment).where(Assignment.source == "auto_capture")).actor_id is None
    # The assigned telecaller sees the alert; the other telecaller does not.
    first_owner = "caller" if owners[0] == ids["caller"] else "caller2"
    other = "caller2" if first_owner == "caller" else "caller"
    names = lambda role: [  # noqa: E731
        i["description"] for i in c[role].get("/api/notifications/inbox").json()["items"] if i["kind"] == "new_enquiry"
    ]
    assert "Auto 0" in names(first_owner) and "Auto 0" not in names(other)
    assert {"Auto 0", "Auto 1", "Auto 2", "Manual Pick"} <= set(names("admin"))
    for role in ["caller", "caller2"]:
        assert c["admin"].patch(f"/api/team/{ids[role]}", json={"active": False}).status_code == 200
    public().post(url, headers={"X-Webhook-Token": key}, json={"name": "Nobody Free", "phone": "+919811100030"})
    assert leads_named(ids["org"], "Nobody Free")[0].owner_id is None


def test_google_ads_webhook_verifies_key_handles_test_data_and_maps_columns(env):
    c, ids = env
    key = c["admin"].post("/api/lead-capture/google-ads/key").json()["key"]
    url = f"/api/capture/{ids['org']}/google-ads"
    body = {
        "lead_id": "TeSter-123",
        "api_version": "1.0",
        "form_id": 40000,
        "campaign_id": 12345,
        "google_key": key,
        "is_test": False,
        "user_column_data": [
            {"column_id": "FIRST_NAME", "string_value": "Arjun", "column_name": "First Name"},
            {"column_id": "LAST_NAME", "string_value": "Mehta", "column_name": "Last Name"},
            {"column_id": "PHONE_NUMBER", "string_value": "+919811100040", "column_name": "User Phone"},
            {"column_id": "CITY", "string_value": "Mumbai", "column_name": "City"},
            {"column_id": "EMAIL", "string_value": "arjun@example.com", "column_name": "User Email"},
            {"column_id": "QUESTION_1", "string_value": "3 BHK", "column_name": "Preferred size"},
        ],
    }
    assert public().post(url, json={**body, "google_key": "wrong-key-value"}).status_code == 401
    assert public().post(url, json={**body, "is_test": True}).json() == {}
    assert leads_named(ids["org"], "Arjun Mehta") == []
    assert c["admin"].get("/api/lead-capture").json()["recent"][0]["state"] == "test"
    assert public().post(url, json=body).status_code == 200
    [lead] = leads_named(ids["org"], "Arjun Mehta")
    assert lead.source == "google-ads" and lead.city == "Mumbai" and lead.phone == "+919811100040"
    for text in [
        "Google Ads lead form",
        "User Email: arjun@example.com",
        "Preferred size: 3 BHK",
        "Campaign ID: 12345",
    ]:
        assert text in lead.notes
    public().post(url, json=body)
    assert len(leads_named(ids["org"], "Arjun Mehta")) == 1
    with SessionLocal() as db:
        assert db.scalar(select(Provenance).where(Provenance.provider == "google-ads")).external_id == "TeSter-123"
    assert public().post(url, json=[body, body]).status_code == 422


def test_hosted_form_requires_enablement_consent_and_same_origin_browser(env):
    c, ids = env
    assert c["admin"].get("/api/lead-capture").json()["form"]["url"] == ""
    enabled = c["admin"].put("/api/lead-capture", json={"form_enabled": True}).json()
    form_id = enabled["form"]["url"].rsplit("/", 1)[1]
    assert enabled["form"]["enabled"] is True and len(form_id) >= 20
    assert public().get(f"/api/public/enquiry/{form_id}").json() == {
        "company": "Test Organization",
        "real_estate": False,
    }
    assert public().get("/api/public/enquiry/not-a-real-form").status_code == 404
    url = f"/api/public/enquiry/{form_id}"
    good = {"name": "Form Buyer", "phone": "+919811100050", "consent": True, "purpose": "buy", "message": "Hi"}
    assert public().post(url, json=good).status_code == 403
    assert browser().post(url, headers={"Origin": "https://evil.example"}, json=good).status_code == 403
    assert browser().post(url, json={**good, "consent": False}).status_code == 422
    assert browser().post(url, json={**good, "email": "not-an-email"}).status_code == 422
    assert browser().post(url, json={**good, "website": "http://spam"}).json()["ok"] is True
    assert leads_named(ids["org"], "Form Buyer") == []
    response = browser().post(url, json=good)
    assert response.status_code == 200 and response.json() == {"ok": True, "company": "Test Organization"}
    browser().post(url, json=good)
    [lead] = leads_named(ids["org"], "Form Buyer")
    assert lead.notes.count("Enquiry via Website enquiry form") == 1
    assert "Looking to: buy" in lead.notes and "Consent: Agreed to be contacted" in lead.notes
    replaced = c["admin"].post("/api/lead-capture/form/new-link").json()
    assert replaced["form"]["url"] != enabled["form"]["url"]
    assert public().get(url).status_code == 404
    c["admin"].put("/api/lead-capture", json={"form_enabled": False})
    assert public().get("/api/public/enquiry/" + replaced["form"]["url"].rsplit("/", 1)[1]).status_code == 404


def test_hosted_form_rate_limit_per_company(env):
    c, ids = env
    form_id = c["admin"].put("/api/lead-capture", json={"form_enabled": True}).json()["form"]["url"].rsplit("/", 1)[1]
    url = f"/api/public/enquiry/{form_id}"
    for index in range(30):
        response = browser().post(
            url, json={"name": f"Burst {index}", "phone": f"+9198111{index:05d}", "consent": True}
        )
        assert response.status_code == 200, response.text
    limited = browser().post(url, json={"name": "One Too Many", "phone": "+919811199999", "consent": True})
    assert limited.status_code == 429
    with SessionLocal() as db:
        assert db.scalar(select(SyncRun).order_by(SyncRun.created_at.desc())).imported == 1


def test_alert_clears_on_response_and_dashboard_reports_speed_to_lead(env):
    c, ids = env
    key = c["admin"].post("/api/lead-capture/website/key").json()["key"]
    url = f"/api/capture/{ids['org']}/website"
    for name, number in [("Fast Reply", "+919811100060"), ("Slow Reply", "+919811100061")]:
        public().post(url, headers={"X-Webhook-Token": key}, json={"name": name, "phone": number})
    fast, slow = leads_named(ids["org"], "Fast Reply")[0], leads_named(ids["org"], "Slow Reply")[0]
    c["admin"].post("/api/leads/assign", json={"lead_ids": [fast.id, slow.id], "owner_id": ids["caller"]})
    kinds = {i["description"]: i["kind"] for i in c["caller"].get("/api/notifications/inbox").json()["items"]}
    assert kinds["Fast Reply"] == "new_enquiry" and kinds["Slow Reply"] == "new_enquiry"
    # An unanswered outgoing call still counts as the first response.
    synced = c["caller"].post(
        "/api/phone-calls/sync",
        json={
            "device_id": "android-capture-001",
            "calls": [
                {
                    "device_call_id": "capture-1",
                    "phone": fast.phone,
                    "direction": "outgoing",
                    "result": "missed",
                    "started_at": now().isoformat(),
                    "duration": 0,
                }
            ],
        },
    )
    assert synced.status_code == 200, synced.text
    items = c["caller"].get("/api/notifications/inbox").json()["items"]
    assert "Fast Reply" not in [i["description"] for i in items if i["kind"] == "new_enquiry"]
    with SessionLocal.begin() as db:
        db.get(Lead, slow.id).created_at = now() - timedelta(minutes=40)
    outcome = c["caller"].post(
        f"/api/leads/{slow.id}/outcomes",
        json={
            "outcome": "follow-up",
            "follow_up": (now() + timedelta(days=1)).isoformat(),
            "request_id": str(uuid4()),
        },
    )
    assert outcome.status_code == 201, outcome.text
    assert not [i for i in c["caller"].get("/api/notifications/inbox").json()["items"] if i["kind"] == "new_enquiry"]
    speed = c["admin"].get("/api/dashboard?days=7").json()["speed_to_lead"]
    assert speed["captured"] == 2 and speed["responded"] == 2 and speed["awaiting"] == 0
    assert speed["within_target"] == 1 and speed["target_minutes"] == 15
    assert 15 < speed["median_minutes"] < 25
    # A repeat enquiry after the response raises the alert again until the next contact.
    public().post(url, headers={"X-Webhook-Token": key}, json={"name": "Slow Again", "phone": slow.phone})
    items = c["caller"].get("/api/notifications/inbox").json()["items"]
    assert ("Slow Reply", "new_enquiry") in [(i["description"], i["kind"]) for i in items]
    # Old uncontacted captured leads are not also listed as first-contact reminders.
    with SessionLocal.begin() as db:
        lead = db.get(Lead, slow.id)
        lead.created_at = now() - timedelta(days=3)
        lead.follow_up = lead.last_contact = lead.first_response_at = None
    kinds = [
        i["kind"]
        for i in c["caller"].get("/api/notifications/inbox").json()["items"]
        if i["description"] == "Slow Reply"
    ]
    assert kinds == ["new_enquiry"]
