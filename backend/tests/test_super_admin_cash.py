from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.billing import today
from app.db import SessionLocal
from app.main import app
from app.models import Audit, SubscriptionPayment, User
from conftest import PASSWORD
from test_company_billing import configure, payment, picture, plan


def cash_config(owner, **extra):
    response = owner.put(
        "/api/platform/billing/config",
        json={
            "upi_enabled": False,
            "cod_enabled": True,
            "cod_instructions": "Arrange collection with the platform office. QA only.",
            **extra,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def cash(client, chosen, request_id="cash-request-1", **extra):
    return client.post(
        "/api/billing/payments",
        data={
            "plan_id": chosen["id"],
            "cycle": "monthly",
            "payment_method": "cod",
            "request_id": request_id,
            "quoted_amount": chosen["monthly_price"],
            **extra,
        },
    )


def create_admin(owner, org, **extra):
    return owner.post(
        f"/api/platform/organizations/{org}/admins",
        json={
            "name": "Second Company Admin",
            "phone": "+919900008888",
            "password": PASSWORD,
            "role": "admin",
            **extra,
        },
    )


def test_cash_request_needs_no_qr_and_activation_requires_confirmed_receipt(env):
    c, ids = env
    config = cash_config(c["owner"])
    assert config["cod_enabled"] and not config["upi_enabled"] and not config["qr_ready"]
    chosen = plan(c["owner"])
    result = cash(c["admin"], chosen)
    assert result.status_code == 201, result.text
    item = result.json()
    assert item["payment_method"] == "cod" and item["reference"] is None and item["receipt_id"] is None
    assert item["status"] == "pending" and c["admin"].get("/api/billing").json()["subscription"] is None
    path = f"/api/platform/payments/{item['id']}/review"
    body = {"status": "approved", "note": "Cash physically collected at office"}
    assert c["admin"].post(path, json={**body, "cash_received": True}).status_code == 403
    denied = c["owner"].post(path, json=body)
    assert denied.status_code == 422 and denied.json()["error"]["code"] == "cash_confirmation_required"
    assert c["admin"].get("/api/billing").json()["payments"][0]["status"] == "pending"
    assert c["owner"].post(path, json={**body, "cash_received": True}).status_code == 200
    subscription = c["admin"].get("/api/billing").json()["subscription"]
    assert subscription["status"] == "active" and subscription["plan_id"] == chosen["id"]
    assert c["owner"].post(path, json={**body, "cash_received": True}).status_code == 409
    assert c["admin"].get("/api/billing").json()["subscription"]["ends_on"] == subscription["ends_on"]
    with SessionLocal() as db:
        audit = db.scalar(select(Audit).where(Audit.org_id == ids["org"], Audit.action == "payment_approved"))
        assert audit.details["payment_method"] == "cod" and audit.details["cash_received"] is True


def test_cash_idempotency_pending_and_reference_rules(env):
    c, _ = env
    cash_config(c["owner"])
    chosen = plan(c["owner"])
    assert cash(c["admin"], chosen, reference="FAKE-UPI-REF").status_code == 422
    assert (
        c["admin"]
        .post(
            "/api/billing/payments",
            data={
                "plan_id": chosen["id"],
                "cycle": "monthly",
                "payment_method": "cod",
                "request_id": "cash-with-receipt",
                "quoted_amount": "1999",
            },
            files={"receipt": ("fake-cash-receipt.png", picture())},
        )
        .status_code
        == 422
    )
    first = cash(c["admin"], chosen).json()
    assert cash(c["admin"], chosen).json()["id"] == first["id"]
    assert cash(c["admin"], chosen, quoted_amount="2999").json()["error"]["code"] == "request_conflict"
    changed = cash(c["admin"], chosen, payment_method="upi", reference="REAL-UPI-123")
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "request_conflict"
    assert cash(c["admin"], chosen, "new-cash-request").json()["error"]["code"] == "payment_pending"
    # NULL cash references do not collide between independent company requests.
    second = cash(c["other"], chosen)
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    assert len(c["other"].get("/api/billing").json()["payments"]) == 1


def test_payment_method_configuration_and_role_guards(env):
    c, _ = env
    chosen = plan(c["owner"])
    assert cash(c["admin"], chosen).json()["error"]["code"] == "payment_method_unavailable"
    assert cash_config(c["owner"])["cod_enabled"]
    assert payment(c["admin"], chosen).json()["error"]["code"] == "payment_method_unavailable"
    assert cash(c["caller"], chosen).status_code == 403
    assert cash(c["manager"], chosen).status_code == 403
    assert c["admin"].put("/api/platform/billing/config", json={"cod_enabled": True}).status_code == 403
    first = cash(c["admin"], chosen).json()
    cash_config(c["owner"], cod_enabled=False)
    assert cash(c["admin"], chosen).json()["id"] == first["id"]
    assert cash(c["other"], chosen).status_code == 409
    assert cash(c["other"], chosen, payment_method="card").status_code == 422
    assert cash(c["other"], chosen, quoted_amount="invalid").status_code == 422


def test_cash_rejection_allows_corrected_request_and_one_concurrent_approval(env):
    c, _ = env
    cash_config(c["owner"])
    chosen = plan(c["owner"])
    first = cash(c["admin"], chosen).json()
    assert (
        c["owner"]
        .post(f"/api/platform/payments/{first['id']}/review", json={"status": "rejected", "note": "Cash not collected"})
        .status_code
        == 200
    )
    assert c["admin"].get("/api/billing").json()["subscription"] is None
    item = cash(c["admin"], chosen, "resubmitted-cash-request").json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda _: (
                    c["owner"]
                    .post(
                        f"/api/platform/payments/{item['id']}/review",
                        json={"status": "approved", "note": "Cash collected", "cash_received": True},
                    )
                    .status_code
                ),
                range(2),
            )
        )
    assert sorted(statuses) == [200, 409]


def test_existing_upi_requests_stay_compatible_and_cash_requires_quoted_price(env):
    c, _ = env
    configure(c["owner"])
    chosen = plan(c["owner"])
    legacy = payment(c["admin"], chosen)
    assert legacy.status_code == 201 and legacy.json()["payment_method"] == "upi"
    assert (
        c["owner"]
        .post(
            f"/api/platform/payments/{legacy.json()['id']}/review",
            json={"status": "approved", "note": "UPI receiving statement checked"},
        )
        .status_code
        == 200
    )
    cash_config(c["owner"])
    assert cash(c["admin"], chosen, quoted_amount="1").json()["error"]["code"] == "price_changed"
    assert cash(c["admin"], chosen, quoted_amount="NaN").status_code == 409
    assert cash(c["admin"], chosen, cycle="weekly").status_code == 422
    assert cash(c["admin"], chosen, request_id="short").status_code == 422


def test_owner_creates_admin_scopes_role_and_retains_credentials_privately(env):
    c, ids = env
    path = f"/api/platform/organizations/{ids['org']}/admins"
    payload = {"name": "Company Admin Two", "phone": "+919900008888", "password": PASSWORD, "role": "admin"}
    for role in ["admin", "manager", "caller", "other"]:
        assert c[role].post(path, json=payload).status_code == 403
    result = c["owner"].post(path, json=payload)
    assert result.status_code == 201, result.text
    user = result.json()
    assert user["role"] == "admin" and user["org_id"] == ids["org"]
    assert PASSWORD not in result.text and "password_hash" not in result.text
    assert c["owner"].post(path, json=payload).status_code == 409
    assert create_admin(c["owner"], ids["org"], role="telecaller").status_code == 422
    assert create_admin(c["owner"], ids["org"], phone="bad-number").status_code == 422
    assert create_admin(c["owner"], ids["org"], password="short").status_code == 422
    with TestClient(app) as login:
        auth = login.post("/api/auth/login", json={"phone": user["phone"], "password": PASSWORD})
        assert auth.status_code == 200 and auth.json()["role"] == "admin"
        assert auth.json()["organization"]["id"] == ids["org"]
    with SessionLocal() as db:
        audit = db.scalar(select(Audit).where(Audit.entity_id == user["id"], Audit.action == "admin_created"))
        assert audit.actor_id == ids["owner"] and PASSWORD not in str(audit.details)


def test_admin_edit_resets_sessions_only_for_actual_login_changes(env):
    c, ids = env
    path = f"/api/platform/organizations/{ids['org']}/admins/{ids['admin']}"
    assert c["owner"].patch(path, json={"name": "Renamed Admin", "phone": "+919900001001"}).status_code == 200
    assert c["admin"].get("/api/auth/me").status_code == 200
    assert c["owner"].patch(path, json={"phone": "+919900001005"}).status_code == 409
    assert c["owner"].patch(path, json={"role": "owner"}).status_code == 422
    assert c["owner"].patch(path, json={"name": None}).status_code == 422
    new_password = "ReplacementPassword!2026"
    changed = c["owner"].patch(path, json={"phone": "+919900008889", "password": new_password})
    assert changed.status_code == 200 and new_password not in changed.text
    assert c["admin"].get("/api/auth/me").status_code == 401
    assert c["caller"].get("/api/auth/me").status_code == 200
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"phone": "+919900008889", "password": PASSWORD}).status_code == 401
        assert (
            client.post("/api/auth/login", json={"phone": "+919900008889", "password": new_password}).status_code == 200
        )
    assert (
        c["owner"]
        .patch(f"/api/platform/organizations/{ids['other_org']}/admins/{ids['admin']}", json={"name": "Cross company"})
        .status_code
        == 404
    )
    assert (
        c["owner"]
        .patch(f"/api/platform/organizations/{ids['org']}/admins/{ids['caller']}", json={"name": "Wrong role"})
        .status_code
        == 404
    )


def test_admin_last_admin_and_seat_guards_are_serialized(env):
    c, ids = env
    base = f"/api/platform/organizations/{ids['org']}"
    assert c["owner"].patch(base + "/admins/" + ids["admin"], json={"active": False}).status_code == 409
    second = create_admin(c["owner"], ids["org"]).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda user: c["owner"].patch(base + "/admins/" + user, json={"active": False}).status_code,
                [ids["admin"], second["id"]],
            )
        )
    assert sorted(statuses) == [200, 409]
    with SessionLocal() as db:
        admins = list(
            db.scalars(select(User).where(User.org_id == ids["org"], User.role == "admin", User.active.is_(True)))
        )
        assert len(admins) == 1
    terms = {"status": "trial", "seats": 4, "starts_on": str(today()), "ends_on": str(today() + timedelta(days=7))}
    assert c["owner"].put(base + "/subscription", json=terms).status_code == 200
    assert create_admin(c["owner"], ids["org"], phone="+919900008887").status_code == 409
    inactive = next(user for user in [ids["admin"], second["id"]] if user != admins[0].id)
    assert c["owner"].patch(base + "/admins/" + inactive, json={"active": True}).status_code == 409


def test_logo_replace_remove_and_failure_preserve_company_profile(env):
    c, ids = env
    path = f"/api/platform/organizations/{ids['org']}/logo"
    assert (
        c["owner"]
        .patch(
            f"/api/platform/organizations/{ids['org']}",
            json={"brand_name": "Retained Brand", "profile": {"city": "Panipat"}},
        )
        .status_code
        == 200
    )
    first = c["owner"].post(path, files={"file": ("logo.png", picture())}).json()
    assert c["owner"].post(path, files={"file": ("fake.png", b"not an image")}).status_code == 422
    assert c["owner"].get(path).status_code == 200
    replacement = c["owner"].post(path, files={"file": ("replacement.png", picture())}).json()
    assert replacement["settings"]["logo_id"] != first["settings"]["logo_id"]
    assert c["other"].delete(path).status_code == 403
    assert c["owner"].delete(path).status_code == 200
    assert c["owner"].delete(path).status_code == 200
    assert c["owner"].get(path).status_code == 404
    detail = c["owner"].get(f"/api/platform/organizations/{ids['org']}").json()["organization"]
    assert "logo_id" not in detail["settings"]
    assert (
        detail["settings"]["brand_name"] == "Retained Brand"
        and detail["settings"]["company_profile"]["city"] == "Panipat"
    )


def test_payment_method_migration_preserves_legacy_upi_and_blocks_lossy_cash_rollback(env):
    c, _ = env
    configure(c["owner"])
    chosen = plan(c["owner"])
    item = payment(c["admin"], chosen).json()
    command.downgrade(Config("alembic.ini"), "0006")
    command.upgrade(Config("alembic.ini"), "head")
    current = c["admin"].get("/api/billing").json()
    assert current["payments"][0]["reference"] == item["reference"]
    assert current["payments"][0]["payment_method"] == "upi"
    assert current["config"]["upi_enabled"] and not current["config"]["cod_enabled"] and current["config"]["qr_ready"]
    assert (
        c["owner"]
        .post(f"/api/platform/payments/{item['id']}/review", json={"status": "rejected", "note": "Migration fixture"})
        .status_code
        == 200
    )
    cash_config(c["owner"])
    assert cash(c["admin"], chosen, "migration-cash-request").status_code == 201
    import pytest

    with pytest.raises(RuntimeError, match="cash payment history"):
        command.downgrade(Config("alembic.ini"), "0006")
    with SessionLocal() as db:
        assert db.scalar(select(SubscriptionPayment).where(SubscriptionPayment.payment_method == "cod"))
    command.check(Config("alembic.ini"))
