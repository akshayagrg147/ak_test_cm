from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal, now
from app.main import app
from app.models import AuthSession, User
from app.security import decrypt
from conftest import PASSWORD, make_lead


@pytest.mark.parametrize(
    "role,path",
    [
        ("caller", "/api/team"),
        ("caller", "/api/payroll?month=2026-10"),
        ("manager", "/api/payroll?month=2026-10"),
        ("caller", "/api/audit"),
        ("caller", "/api/backups"),
        ("caller", "/api/automations"),
        ("manager", "/api/platform"),
        ("owner", "/api/leads"),
        ("owner", "/api/team"),
    ],
)
def test_role_boundaries(env, role, path):
    clients, _ = env
    assert clients[role].get(path).status_code == 403


def test_organization_isolation_and_scoped_files(env):
    clients, ids = env
    lead = make_lead(clients["caller"])
    for user in ["caller2", "other"]:
        assert clients[user].get("/api/leads/" + lead["id"]).status_code == 404
        assert clients[user].get("/api/leads/" + lead["id"] + "/history").status_code == 404
        assert clients[user].get("/api/leads").json()["total"] == 0
    assert clients["admin"].get("/api/leads?owner_id=" + ids["caller"]).json()["total"] == 1
    assert clients["other"].get("/api/analytics").json()["metrics"]["leads"] == 0
    assert b"Example Customer" not in clients["other"].get("/api/leads/export").content


@pytest.mark.parametrize("forged", [{"role": "admin"}, {"org_id": "fake"}, {"owner_id": "fake"}, {"active": False}])
def test_no_forged_lead_fields(env, forged):
    clients, _ = env
    assert (
        clients["caller"].post("/api/leads", json={"name": "Forged lead", "phone": "9810001234", **forged}).status_code
        == 422
    )


def test_login_normalization_invalid_and_refresh_rotation(env):
    clients, _ = env
    c = clients["caller"]
    token = c.headers["Authorization"]
    old = c.cookies.get("crm_refresh")
    r = c.post("/api/auth/refresh")
    assert r.status_code == 200
    assert c.cookies.get("crm_refresh") != old
    with TestClient(app) as replay:
        replay.cookies.set("crm_refresh", old)
        assert replay.post("/api/auth/refresh", headers={"X-Requested-With": "TalkoCRM"}).status_code == 401
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/leads", headers={"Authorization": token}).status_code == 401
    assert TestClient(app).post("/api/auth/login", json={"phone": "9900001003", "password": "wrong"}).status_code == 401
    for normalized in ["9900001003", "+91 99000 01003"]:
        assert (
            TestClient(app).post("/api/auth/login", json={"phone": normalized, "password": PASSWORD}).status_code == 200
        )


def test_csrf_and_rate_limiting(env):
    clients, _ = env
    c = clients["caller"]
    assert c.post("/api/auth/refresh", headers={"X-Requested-With": ""}).status_code == 403
    assert c.post("/api/auth/refresh", headers={"Origin": "https://evil.invalid"}).status_code == 403
    anon = TestClient(app)
    for _ in range(10):
        assert anon.post("/api/auth/login", json={"phone": "9900001003", "password": "wrong"}).status_code == 401
    assert anon.post("/api/auth/login", json={"phone": "9900001003", "password": PASSWORD}).status_code == 429


def test_two_factor_lifecycle_and_replay(env):
    clients, _ = env
    c = clients["caller"]
    setup = c.post("/api/auth/2fa/setup", json={"password": PASSWORD})
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    assert c.post("/api/auth/2fa/enable", json={"password": PASSWORD, "code": "000000"}).status_code == 401
    assert c.post("/api/auth/2fa/enable", json={"password": PASSWORD, "code": code}).status_code == 200
    r = TestClient(app).post("/api/auth/login", json={"phone": "9900001003", "password": PASSWORD})
    assert r.json()["challenge_required"]
    assert (
        TestClient(app)
        .post(
            "/api/auth/login",
            json={"phone": "9900001003", "password": PASSWORD, "challenge": r.json()["challenge"], "code": code},
        )
        .status_code
        == 401
    )
    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.phone == "+919900001003"))
        user.totp_last_step = 0
        assert decrypt(user.totp_secret) == secret
    r2 = TestClient(app).post(
        "/api/auth/login",
        json={"phone": "9900001003", "password": PASSWORD, "challenge": r.json()["challenge"], "code": code},
    )
    assert r2.status_code == 200
    assert c.post("/api/auth/2fa/disable", json={"password": PASSWORD, "code": code}).status_code == 200
    assert not c.get("/api/auth/me").json()["user"]["totp_enabled"]


def test_last_admin_concurrent_demotion(env):
    clients, ids = env
    r = clients["admin"].post(
        "/api/team", json={"name": "Second Admin", "phone": "9900001099", "password": PASSWORD, "role": "admin"}
    )
    assert r.status_code == 201
    second = r.json()["id"]
    # Two concurrent requests by one admin must not both deactivate the final two admins.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda uid: clients["admin"].patch("/api/team/" + uid, json={"active": False}).status_code,
                [ids["admin"], second],
            )
        )
    assert sum(status == 200 for status in results) == 1
    assert all(status in [200, 401, 409] for status in results)
    with SessionLocal() as db:
        admins = list(
            db.scalars(select(User).where(User.org_id == ids["org"], User.active.is_(True), User.role == "admin"))
        )
        assert len(admins) == 1


def test_manager_cannot_change_roles_or_admin_state(env):
    clients, ids = env
    for target, body in [
        (ids["caller"], {"role": "admin"}),
        (ids["admin"], {"active": False}),
        (ids["caller"], {"password": "OtherPassword123!"}),
    ]:
        assert clients["manager"].patch("/api/team/" + target, json=body).status_code == 403
    assert (
        clients["manager"]
        .post(
            "/api/team", json={"name": "Escalated User", "phone": "9900001098", "password": PASSWORD, "role": "admin"}
        )
        .status_code
        == 403
    )


def test_suspension_and_deactivation_revoke_old_tokens(env):
    clients, ids = env
    assert clients["admin"].patch("/api/team/" + ids["caller"], json={"active": False}).status_code == 200
    assert clients["caller"].get("/api/leads").status_code == 401
    assert clients["caller"].post("/api/auth/refresh").status_code == 401
    assert (
        clients["owner"].patch("/api/platform/organizations/" + ids["org"], json={"active": False}).status_code == 200
    )
    assert clients["admin"].get("/api/leads").status_code == 401
    assert clients["owner"].patch("/api/platform/organizations/" + ids["org"], json={"active": True}).status_code == 200
    assert clients["admin"].get("/api/leads").status_code == 401


def test_support_is_explicit_audited_and_exitable(env):
    clients, ids = env
    owner = clients["owner"]
    r = owner.post("/api/platform/organizations/" + ids["org"] + "/support")
    assert r.status_code == 200
    assert r.json()["support"] and r.json()["role"] == "admin"
    owner.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    assert owner.get("/api/leads").status_code == 200
    assert owner.get("/api/audit").json()[0]["action"] == "support_started"
    r = owner.post("/api/auth/support/exit")
    assert r.status_code == 200
    owner.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    assert owner.get("/api/leads").status_code == 403


def test_password_change_revokes_other_sessions(env):
    clients, _ = env
    c = clients["caller"]
    second = TestClient(app)
    r = second.post("/api/auth/login", json={"phone": "9900001003", "password": PASSWORD})
    second.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    assert (
        c.post("/api/auth/password", json={"current": PASSWORD, "password": "NewTestPassword!123"}).status_code == 200
    )
    assert second.get("/api/leads").status_code == 401
    assert c.get("/api/leads").status_code == 200


def test_expired_refresh_rejected(env):
    clients, ids = env
    with SessionLocal.begin() as db:
        for s in db.scalars(select(AuthSession).where(AuthSession.user_id == ids["caller"])):
            s.expires_at = now() - timedelta(seconds=1)
    assert clients["caller"].get("/api/leads").status_code == 401
    assert clients["caller"].post("/api/auth/refresh").status_code == 401
