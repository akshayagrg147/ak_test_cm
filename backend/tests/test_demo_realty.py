import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import demo_realty
from app.db import SessionLocal
from app.main import app
from app.models import Booking, CompanySubscription, Lead, Organization, Property, SiteVisit, User
from app.security import passwords

from conftest import PASSWORD


def counts(org_id):
    with SessionLocal() as db:
        return {
            model.__tablename__: db.scalar(select(func.count()).select_from(model).where(model.org_id == org_id))
            for model in (Lead, Property, SiteVisit, Booking, User)
        }


def login(phone):
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"phone": phone, "password": PASSWORD})
    assert r.status_code == 200, r.text
    client.headers.update({"Authorization": "Bearer " + r.json()["access_token"], "X-Requested-With": "TalkoCRM"})
    return client


def test_demo_realty_create_browse_and_reset(env):
    _, ids = env
    other_before = counts(ids["org"])
    demo_realty.create()
    demo = demo_realty.DEMO_ID
    assert counts(demo) == {"leads": 30, "properties": 10, "site_visits": 5, "bookings": 1, "users": 4}
    with SessionLocal() as db:
        org = db.get(Organization, demo)
        assert org.settings["industry"] == "real_estate"
        assert db.scalar(select(CompanySubscription).where(CompanySubscription.org_id == demo)).status == "active"
        assert all(lead.notes == demo_realty.FICTIONAL for lead in db.scalars(select(Lead).where(Lead.org_id == demo)))
        assert db.scalar(select(Property).where(Property.reference == "DEMO-P01", Property.org_id == demo)).status == "reserved"
        # Nobody can sign in until the owner sets real passwords.
        users = list(db.scalars(select(User).where(User.org_id == demo)))
        assert not any(passwords.verify(PASSWORD, u.password_hash) for u in users)
    with SessionLocal.begin() as db:
        for user in db.scalars(select(User).where(User.org_id == demo)):
            user.password_hash = passwords.hash(PASSWORD)

    admin, caller = login("+919000000901"), login("+919000000902")
    for path in ["/api/dashboard", "/api/leads", "/api/properties", "/api/site-visits", "/api/bookings",
                 "/api/real-estate/overview", "/api/onboarding", "/api/notifications/inbox", "/api/reports/analytics"]:
        r = admin.get(path)
        assert r.status_code in (200, 404), (path, r.status_code, r.text)
        assert r.status_code == 200 or path == "/api/reports/analytics", (path, r.text)
    leads = caller.get("/api/leads").json()
    items = leads["items"] if isinstance(leads, dict) else leads
    assert items and all(item["owner_id"] for item in items)  # a caller sees only assigned leads
    lead_id = items[0]["id"]
    assert caller.get(f"/api/leads/{lead_id}/history").status_code == 200

    # A prospect edits the demo; reset restores it and keeps logins and passwords.
    with SessionLocal.begin() as db:
        db.get(Lead, lead_id).name = "Changed by prospect"
    demo_realty.reset()
    assert counts(demo) == {"leads": 30, "properties": 10, "site_visits": 5, "bookings": 1, "users": 4}
    with SessionLocal() as db:
        assert not db.scalar(select(Lead).where(Lead.org_id == demo, Lead.name == "Changed by prospect"))
    login("+919000000901")
    assert counts(ids["org"]) == other_before

    with pytest.raises(SystemExit, match="already exists"):
        demo_realty.create()


def test_demo_realty_refuses_used_phones_and_foreign_org(env):
    _, ids = env
    with SessionLocal.begin() as db:
        db.add(User(name="Real person", role="admin", org_id=ids["org"], phone="+919000000902", password_hash="x"))
    with pytest.raises(SystemExit, match="already in use"):
        demo_realty.create()
    with SessionLocal() as db:
        assert db.get(Organization, demo_realty.DEMO_ID) is None
    with pytest.raises(SystemExit, match="does not exist"):
        demo_realty.reset()
