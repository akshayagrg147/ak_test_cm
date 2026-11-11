"""Getting-started progress, trial countdown and payment readiness for customer-facing guidance."""

from datetime import timedelta

from sqlalchemy import select

from app.billing import today
from app.db import SessionLocal
from app.models import CompanySubscription, Organization
from conftest import PASSWORD, make_lead
from test_company_billing import configure, plan


def create_company(owner, trial_days=3, **profile):
    response = owner.post(
        "/api/platform/organizations",
        json={
            "name": "Checklist Realty",
            "industry": "real_estate",
            "profile": profile,
            "admin": {"name": "Checklist Admin", "phone": "+919900007001", "password": PASSWORD, "role": "admin"},
            "trial_days": trial_days,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["organization"]


def test_onboarding_reports_real_setup_progress_and_is_admin_only(env):
    c, ids = env
    for role in ["manager", "caller", "owner"]:
        assert c[role].get("/api/onboarding").status_code == 403
    data = c["admin"].get("/api/onboarding").json()
    assert data["profile"] == {
        "filled": 0,
        "total": 9,
        "missing": [
            "contact_name",
            "email",
            "phone",
            "city",
            "state",
            "address",
            "website",
            "rera_number",
            "gst_number",
        ],
    }
    assert data["telecallers"] == 2
    assert data["members"] == 4
    assert data["leads"] == 0 and data["properties"] == 0
    assert data["capture"] is False
    assert c["admin"].put("/api/lead-capture", json={"form_enabled": True}).status_code == 200
    assert c["admin"].get("/api/onboarding").json()["capture"] is True
    c["admin"].put("/api/lead-capture", json={"form_enabled": False})
    c["admin"].post("/api/lead-capture/google-ads/key")
    assert c["admin"].get("/api/onboarding").json()["capture"] is True
    assert data["subscription"] is None
    assert data["payments"] == {"plans": 0, "upi_ready": False, "cod_ready": False, "ready": False}

    make_lead(c["admin"])
    assert c["admin"].put("/api/company-profile", json={"city": "Pune", "email": "a@example.com"}).status_code == 200
    assert c["admin"].patch(f"/api/team/{ids['caller2']}", json={"active": False}).status_code == 200
    data = c["admin"].get("/api/onboarding").json()
    assert data["leads"] == 1
    assert data["profile"]["filled"] == 2 and "city" not in data["profile"]["missing"]
    assert data["telecallers"] == 1
    # Another company's data never leaks into this checklist.
    assert c["other"].get("/api/onboarding").json()["leads"] == 0


def test_trial_days_left_and_platform_attention_counts(env):
    c, _ = env
    org = create_company(c["owner"], trial_days=3, city="Mumbai")
    platform = c["owner"].get("/api/platform").json()
    company = next(o for o in platform["organizations"] if o["id"] == org["id"])
    assert company["subscription"]["days_left"] == 2
    assert platform["ending_soon"] == 1 and platform["expired"] == 0

    with SessionLocal.begin() as db:
        subscription = db.scalar(select(CompanySubscription).where(CompanySubscription.org_id == org["id"]))
        subscription.ends_on = today() - timedelta(days=1)
    platform = c["owner"].get("/api/platform").json()
    company = next(o for o in platform["organizations"] if o["id"] == org["id"])
    assert company["subscription"]["effective_status"] == "expired"
    assert company["subscription"]["days_left"] == -1
    assert platform["ending_soon"] == 0 and platform["expired"] == 1

    admin = c["owner"].__class__(c["owner"].app)
    login = admin.post("/api/auth/login", json={"phone": "+919900007001", "password": PASSWORD})
    admin.headers.update({"Authorization": "Bearer " + login.json()["access_token"], "X-Requested-With": "TalkoCRM"})
    data = admin.get("/api/onboarding").json()
    assert data["subscription"]["days_left"] == -1
    assert data["profile"]["filled"] == 1
    with SessionLocal() as db:
        assert db.get(Organization, org["id"]).settings["company_profile"]["city"] == "Mumbai"
    admin.close()


def test_payment_readiness_requires_a_published_plan_and_a_usable_method(env):
    c, _ = env
    readiness = lambda: c["owner"].get("/api/platform").json()["payments"]  # noqa: E731
    assert readiness()["ready"] is False
    # UPI defaults to enabled, but without a QR and payee it cannot take payments.
    chosen = plan(c["owner"])
    assert readiness() == {"plans": 1, "upi_ready": False, "cod_ready": False, "ready": False}
    configure(c["owner"])
    assert readiness() == {"plans": 1, "upi_ready": True, "cod_ready": False, "ready": True}
    assert c["owner"].put(f"/api/platform/plans/{chosen['id']}", json={
        "name": chosen["name"],
        "monthly_price": chosen["monthly_price"],
        "yearly_price": chosen["yearly_price"],
        "seats": chosen["seats"],
        "active": False,
    }).status_code == 200
    assert readiness()["ready"] is False
    assert c["admin"].get("/api/onboarding").json()["payments"]["plans"] == 0


def test_interactive_api_documentation_is_disabled_in_production(monkeypatch):
    import importlib

    import app.config
    import app.main

    assert app.main.app.docs_url == "/api/docs"
    monkeypatch.setattr(app.config.settings, "environment", "production")
    monkeypatch.setattr(app.config.settings, "secret_key", "x" * 48)
    monkeypatch.setattr(app.config.settings, "encryption_key", "configured")
    monkeypatch.setattr(app.config.settings, "public_origin", "https://viacrm.in")
    try:
        production = importlib.reload(app.main).app
        assert production.docs_url is None and production.openapi_url is None and production.redoc_url is None
    finally:
        monkeypatch.undo()
        importlib.reload(app.main)
