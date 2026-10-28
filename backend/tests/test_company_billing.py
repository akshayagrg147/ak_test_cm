from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import io

from PIL import Image
from sqlalchemy import select

from app.billing import period_end, today
from app.db import SessionLocal
from app.models import Audit, CompanySubscription, SubscriptionPayment, User
from conftest import PASSWORD


def picture():
    output = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(output, "PNG")
    return output.getvalue()


def plan(owner, **extra):
    response = owner.post(
        "/api/platform/plans",
        json={"name": "Growth", "monthly_price": "1999", "yearly_price": "19990", "seats": 10, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def configure(owner):
    assert (
        owner.put(
            "/api/platform/billing/config",
            json={
                "payee_name": "Example Platform",
                "upi_id": "example@upi",
                "instructions": "Development fixture. Do not pay.",
            },
        ).status_code
        == 200
    )
    assert owner.post("/api/platform/billing/qr", files={"file": ("test-image.png", picture())}).status_code == 200


def payment(client, chosen, reference="TXN-12345", request="payment-request-1", **extra):
    return client.post(
        "/api/billing/payments",
        data={
            "plan_id": chosen["id"],
            "cycle": "monthly",
            "reference": reference,
            "request_id": request,
            "quoted_amount": chosen["monthly_price"],
            **extra,
        },
    )


def test_company_creation_profile_branding_trial_and_role_guards(env):
    c, ids = env
    payload = {
        "name": "Orchard Real Estate",
        "industry": "real_estate",
        "brand_name": "Orchard",
        "profile": {
            "contact_name": "Agency Owner",
            "email": "owner@example.com",
            "city": "Pune",
            "rera_number": "TEST-RERA-001",
        },
        "admin": {"name": "Company Admin", "phone": "+919900005001", "password": PASSWORD, "role": "admin"},
        "trial_days": 7,
    }
    assert c["admin"].post("/api/platform/organizations", json=payload).status_code == 403
    response = c["owner"].post("/api/platform/organizations", json=payload)
    assert response.status_code == 201, response.text
    org = response.json()["organization"]
    detail = c["owner"].get("/api/platform/organizations/" + org["id"]).json()
    assert detail["subscription"]["seats"] == 5
    assert detail["subscription"]["used_seats"] == 1
    assert detail["subscription"]["ends_on"] == str(today() + timedelta(days=6))
    assert org["settings"]["brand_name"] == "Orchard"
    logo = c["owner"].post(
        f"/api/platform/organizations/{org['id']}/logo", files={"file": ("transparent.png", picture())}
    )
    assert logo.status_code == 201, logo.text
    assert "storage_key" not in logo.text
    assert c["owner"].get(f"/api/platform/organizations/{org['id']}/logo").content == picture()
    assert c["other"].get(f"/api/platform/organizations/{org['id']}/logo").status_code == 403
    assert (
        c["owner"]
        .patch(f"/api/platform/organizations/{org['id']}", json={"profile": {"website": "javascript:alert(1)"}})
        .status_code
        == 422
    )
    assert (
        c["owner"]
        .patch(
            f"/api/platform/organizations/{org['id']}",
            json={"brand_name": "Orchard Homes", "profile": {"city": "Mumbai"}},
        )
        .status_code
        == 200
    )
    assert c["owner"].get(f"/api/platform/organizations/{org['id']}").json()["organization"]["settings"]["logo_id"]


def test_company_admin_profile_is_own_scope_and_survives_settings_save(env):
    c, _ = env
    r = c["admin"].put("/api/company-profile", json={"city": "Pune", "email": "team@example.com"})
    assert r.status_code == 200
    assert c["caller"].put("/api/company-profile", json={"city": "Delhi"}).status_code == 403
    assert c["other"].get("/api/settings").json()["settings"].get("company_profile") is None
    assert c["admin"].put("/api/settings", json={"brand_name": "My real estate agency"}).status_code == 200
    assert c["admin"].get("/api/settings").json()["settings"]["company_profile"]["city"] == "Pune"


def test_plans_qr_configuration_validation_and_private_access(env):
    c, _ = env
    p = plan(c["owner"])
    assert c["admin"].get("/api/platform/billing").status_code == 403
    assert c["caller"].get("/api/billing").status_code == 403
    assert c["manager"].get("/api/billing/qr").status_code == 403
    assert c["admin"].get("/api/billing/qr").status_code == 404
    assert payment(c["admin"], p).status_code == 409
    assert c["admin"].post("/api/platform/billing/qr", files={"file": ("test.png", picture())}).status_code == 403
    assert c["owner"].post("/api/platform/billing/qr", files={"file": ("fake.png", b"not PNG")}).status_code == 422
    assert (
        c["owner"]
        .put("/api/platform/billing/config", json={"payee_name": "Example", "upi_id": "not a vpa"})
        .status_code
        == 422
    )
    configure(c["owner"])
    assert c["admin"].get("/api/billing/qr").content == picture()
    assert "qr_storage_key" not in c["owner"].get("/api/platform/billing").text
    assert (
        c["owner"]
        .post("/api/platform/plans", json={"name": "growth", "monthly_price": "1", "yearly_price": "1", "seats": 1})
        .status_code
        == 409
    )
    for extra in [{"monthly_price": "-1"}, {"monthly_price": "NaN"}, {"yearly_price": "0"}, {"seats": 0}]:
        assert (
            c["owner"]
            .post(
                "/api/platform/plans",
                json={
                    **{k: p[k] for k in ["name", "monthly_price", "yearly_price", "seats"]},
                    "name": "Invalid",
                    **extra,
                },
            )
            .status_code
            == 422
        )


def test_payment_is_pending_until_owner_approval_and_duplicates_safe(env):
    c, ids = env
    p = plan(c["owner"])
    configure(c["owner"])
    response = payment(c["admin"], p)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["status"] == "pending"
    assert c["admin"].get("/api/billing").json()["subscription"] is None
    assert payment(c["admin"], p).json()["id"] == item["id"]
    assert payment(c["admin"], p, reference="DIFFERENT-REF").status_code == 409
    assert payment(c["admin"], p, reference="TXN-23456", request="other-request").status_code == 409
    assert payment(c["other"], p, request="other-company").status_code == 409
    assert c["other"].get("/api/billing").json()["payments"] == []
    assert (
        c["admin"]
        .post(f"/api/platform/payments/{item['id']}/review", json={"status": "approved", "note": "Bank verified"})
        .status_code
        == 403
    )
    approved = c["owner"].post(
        f"/api/platform/payments/{item['id']}/review",
        json={"status": "approved", "note": "Matched receiving bank statement"},
    )
    assert approved.status_code == 200, approved.text
    subscription = c["admin"].get("/api/billing").json()["subscription"]
    assert subscription["status"] == "active" and subscription["seats"] == 10
    assert subscription["amount"] == "1999.00"
    assert subscription["ends_on"] == str(period_end(today(), "monthly"))
    assert (
        c["owner"]
        .post(f"/api/platform/payments/{item['id']}/review", json={"status": "approved", "note": "Again"})
        .status_code
        == 409
    )
    with SessionLocal() as db:
        assert db.scalar(select(Audit).where(Audit.action == "payment_approved", Audit.org_id == ids["org"]))


def test_receipt_privacy_and_rejection_retains_evidence(env):
    c, ids = env
    p = plan(c["owner"])
    configure(c["owner"])
    response = c["admin"].post(
        "/api/billing/payments",
        data={
            "plan_id": p["id"],
            "cycle": "monthly",
            "reference": "UPI-RECEIPT-1",
            "request_id": "receipt-test-001",
            "quoted_amount": "1999",
        },
        files={"receipt": ("receipt.png", picture())},
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["receipt_id"]
    assert c["other"].get("/api/files/" + item["receipt_id"]).status_code == 404
    assert c["manager"].get("/api/files/" + item["receipt_id"]).status_code == 403
    assert c["admin"].get("/api/files/" + item["receipt_id"]).content == picture()
    assert c["owner"].get(f"/api/platform/payments/{item['id']}/receipt").content == picture()
    assert c["admin"].delete("/api/files/" + item["receipt_id"]).status_code == 409
    assert (
        c["owner"]
        .post(
            f"/api/platform/payments/{item['id']}/review",
            json={"status": "rejected", "note": "Reference not found in bank statement"},
        )
        .status_code
        == 200
    )
    assert c["admin"].get("/api/billing").json()["subscription"] is None
    assert payment(c["admin"], p, reference="CORRECTED-REF", request="corrected-request").status_code == 201
    assert c["owner"].get(f"/api/platform/payments/{item['id']}/receipt").status_code == 200


def test_server_checks_quote_plan_state_and_transaction_reference(env):
    c, _ = env
    p = plan(c["owner"])
    configure(c["owner"])
    for extra, code in [
        ({"quoted_amount": "1"}, 409),
        ({"quoted_amount": "NaN"}, 409),
        ({"quoted_amount": "invalid"}, 422),
        ({"cycle": "weekly"}, 422),
        ({"reference": "abc"}, 422),
        ({"reference": "with spaces"}, 422),
    ]:
        assert payment(c["admin"], p, **extra).status_code == code
    changed = {k: p[k] for k in ["name", "description", "monthly_price", "yearly_price", "seats", "active"]}
    assert c["owner"].put("/api/platform/plans/" + p["id"], json={**changed, "active": False}).status_code == 200
    assert c["admin"].get("/api/billing").json()["plans"] == []
    assert payment(c["admin"], p).status_code == 422


def test_plan_snapshot_renewal_and_calendar_boundaries(env):
    c, _ = env
    p = plan(c["owner"])
    configure(c["owner"])
    first = payment(c["admin"], p).json()
    # Later catalogue changes cannot alter a pending payment's agreed terms.
    fields = {k: p[k] for k in ["name", "description", "monthly_price", "yearly_price", "seats", "active"]}
    assert (
        c["owner"]
        .put("/api/platform/plans/" + p["id"], json={**fields, "monthly_price": "2999", "seats": 15})
        .status_code
        == 200
    )
    assert (
        c["owner"]
        .post(
            f"/api/platform/payments/{first['id']}/review",
            json={"status": "approved", "note": "Verified original amount"},
        )
        .status_code
        == 200
    )
    before = c["admin"].get("/api/billing").json()["subscription"]
    assert before["amount"] == "1999.00" and before["seats"] == 10
    second = payment(
        c["admin"], {**p, "monthly_price": "2999"}, reference="RENEW-12345", request="renewal-12345"
    ).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: c["owner"].post(
                    f"/api/platform/payments/{second['id']}/review",
                    json={"status": "approved", "note": "Verified renewal"},
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    after = c["admin"].get("/api/billing").json()["subscription"]
    assert after["starts_on"] == before["starts_on"]
    assert after["ends_on"] > before["ends_on"]
    assert period_end(date(2028, 1, 31), "monthly") == date(2028, 2, 28)
    assert period_end(date(2028, 2, 29), "yearly") == date(2029, 2, 27)


def test_seat_limit_includes_admins_and_reactivation(env):
    c, ids = env
    terms = {"status": "trial", "seats": 4, "starts_on": str(today()), "ends_on": str(today() + timedelta(days=14))}
    path = f"/api/platform/organizations/{ids['org']}/subscription"
    assert c["owner"].put(path, json={**terms, "seats": 3}).status_code == 409
    assert c["owner"].put(path, json=terms).status_code == 200
    member = {"name": "Another Agent", "phone": "+919900007777", "role": "telecaller", "password": PASSWORD}
    assert c["admin"].post("/api/team", json=member).status_code == 409
    assert c["admin"].patch("/api/team/" + ids["caller2"], json={"active": False}).status_code == 200
    new = c["admin"].post("/api/team", json=member)
    assert new.status_code == 201, new.text
    assert c["admin"].patch("/api/team/" + ids["caller2"], json={"active": True}).status_code == 409
    assert c["admin"].get("/api/billing").json()["subscription"]["used_seats"] == 4
    assert c["owner"].put(path, json={**terms, "ends_on": str(today() - timedelta(days=1))}).status_code == 422


def test_expired_subscription_is_reported_without_changing_android_auth_contract(env):
    c, ids = env
    with SessionLocal.begin() as db:
        db.add(
            CompanySubscription(
                org_id=ids["org"],
                starts_on=today() - timedelta(days=20),
                ends_on=today() - timedelta(days=1),
                status="trial",
                seats=5,
            )
        )
    assert c["admin"].get("/api/billing").json()["subscription"]["effective_status"] == "expired"
    assert c["caller"].get("/api/phone-calls/contacts").status_code == 200
    assert c["owner"].patch(f"/api/platform/organizations/{ids['org']}", json={"active": False}).status_code == 200
    assert c["caller"].get("/api/phone-calls/contacts").status_code in {401, 403}
    with SessionLocal() as db:
        assert db.get(User, ids["caller"]).active
        assert db.scalar(select(SubscriptionPayment).where(SubscriptionPayment.org_id == ids["org"])) is None


def test_pending_payment_requires_review_before_company_archive(env):
    c, ids = env
    p = plan(c["owner"])
    configure(c["owner"])
    pending = payment(c["admin"], p).json()
    path = "/api/platform/organizations/" + ids["org"]
    assert c["owner"].delete(path, params={"confirmation": "Test Organization"}).status_code == 409
    assert (
        c["owner"]
        .post(
            "/api/platform/payments/" + pending["id"] + "/review",
            json={"status": "rejected", "note": "Unverified test claim resolved before archive"},
        )
        .status_code
        == 200
    )
    assert c["owner"].delete(path, params={"confirmation": "Test Organization"}).status_code == 200
