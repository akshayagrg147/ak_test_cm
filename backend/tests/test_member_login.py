from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal, now
from app.main import app
from app.models import Audit, AuthSession, User
from app.security import decode
from conftest import make_lead


def enter(client, target):
    result = client.post(f"/api/team/{target}/login-as")
    assert result.status_code == 200, result.text
    session = result.json()
    client.headers["Authorization"] = "Bearer " + session["access_token"]
    return session


def test_direct_member_login_has_real_member_permissions_actions_and_admin_audit(env):
    c, ids = env
    own = make_lead(c["caller"], name="Member's customer")
    other = make_lead(c["caller2"], name="Other customer's lead", phone="9810001235")
    original_cookie = c["admin"].cookies.get("crm_refresh")
    result = enter(c["admin"], ids["caller"])
    assert result["user"]["id"] == ids["caller"]
    assert result["role"] == "telecaller"
    assert result["acting_as"]["administrator"]["id"] == ids["admin"]
    assert decode(result["access_token"])["sub"] == ids["admin"]
    assert "parent_session_id" not in result and "refresh_hash" not in str(result)
    assert c["admin"].get("/api/auth/me").json()["user"]["id"] == ids["caller"]
    assert [r["id"] for r in c["admin"].get("/api/leads").json()["items"]] == [own["id"]]
    assert c["admin"].get("/api/leads/" + other["id"]).status_code == 404
    for path in ["/api/team", "/api/payroll?month=2026-10", "/api/audit"]:
        assert c["admin"].get(path).status_code == 403
    response = c["admin"].post(f"/api/leads/{own['id']}/notes", json={"text": "Administrator checked this lead"})
    assert response.status_code == 201, response.text
    assert response.json()["author_id"] == ids["caller"]
    created = make_lead(c["admin"], name="Created through member login", phone="9810001236")
    assert created["owner_id"] == ids["caller"]
    assert c["admin"].post(f"/api/team/{ids['caller2']}/login-as").status_code == 403
    acting_token = c["admin"].headers["Authorization"]
    old_cookie = c["admin"].cookies.get("crm_refresh")
    refreshed = c["admin"].post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["acting_as"]["administrator"]["id"] == ids["admin"]
    assert c["admin"].cookies.get("crm_refresh") != old_cookie
    returned = c["admin"].post("/api/auth/login-as/exit")
    assert returned.status_code == 200, returned.text
    assert returned.json()["user"]["id"] == ids["admin"]
    assert "acting_as" not in returned.json()
    assert c["admin"].get("/api/leads", headers={"Authorization": acting_token}).status_code == 401
    assert c["caller"].get("/api/leads").status_code == 200
    with TestClient(app) as replay:
        for cookie in [old_cookie, original_cookie]:
            replay.cookies.clear()
            replay.cookies.set("crm_refresh", cookie)
            assert replay.post("/api/auth/refresh", headers={"X-Requested-With": "TalkoCRM"}).status_code == 401
    with SessionLocal() as db:
        event = db.scalar(select(Audit).where(Audit.entity_id == own["id"], Audit.action == "note_added"))
        assert event.actor_id == ids["admin"]
        assert event.details["acting_as_user_id"] == ids["caller"]
        assert db.scalar(select(Audit).where(Audit.action == "member_login_started")).actor_id == ids["admin"]
        assert db.scalar(select(Audit).where(Audit.action == "member_login_ended")).actor_id == ids["admin"]


@pytest.mark.parametrize("role", ["caller", "manager", "owner", "other"])
def test_member_login_rejects_unauthorized_or_other_company(env, role):
    c, ids = env
    expected = 404 if role == "other" else 403
    assert c[role].post(f"/api/team/{ids['caller']}/login-as").status_code == expected


def test_member_login_rejects_self_peer_admin_inactive_deleted_and_csrf(env):
    c, ids = env
    assert c["admin"].post(f"/api/team/{ids['admin']}/login-as").status_code == 403
    assert c["admin"].post(f"/api/team/{ids['caller']}/login-as", headers={"X-Requested-With": ""}).status_code == 403
    assert c["admin"].post(f"/api/team/{ids['caller']}/login-as", headers={"Origin": "https://evil.invalid"}).status_code == 403
    for changes in [{"active": False}, {"deleted": True}, {"role": "admin"}]:
        with SessionLocal.begin() as db:
            target = db.get(User, ids["caller"])
            target.active, target.deleted, target.role = True, False, "telecaller"
            for key, value in changes.items():
                setattr(target, key, value)
        result = c["admin"].post(f"/api/team/{ids['caller']}/login-as")
        assert result.status_code == (403 if "role" in changes else 409)


def test_member_login_protects_password_and_authenticator_but_not_normal_member_work(env):
    c, ids = env
    enter(c["admin"], ids["caller"])
    for path in ["/api/auth/password", "/api/auth/2fa/setup", "/api/auth/2fa/enable", "/api/auth/2fa/disable"]:
        response = c["admin"].post(path, json={"current": "unused", "password": "UnusedPassword!123", "code": "000000"})
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "member_security_protected"
    assert c["admin"].post("/api/auth/login-as/exit", headers={"X-Requested-With": ""}).status_code == 403
    assert c["admin"].get("/api/leads").status_code == 200


@pytest.mark.parametrize("change", ["expired", "target_inactive", "target_promoted", "target_moved"])
def test_expired_or_unavailable_member_can_return_to_existing_admin_session(env, change):
    c, ids = env
    result = enter(c["admin"], ids["caller"])
    with SessionLocal.begin() as db:
        session = db.get(AuthSession, decode(result["access_token"])["sid"])
        target = db.get(User, ids["caller"])
        if change == "expired":
            session.acting_until = now() - timedelta(seconds=1)
        elif change == "target_inactive":
            target.active = False
        elif change == "target_promoted":
            target.role = "admin"
        else:
            target.org_id = ids["other_org"]
    assert c["admin"].get("/api/leads").status_code == 401
    restored = c["admin"].post("/api/auth/refresh")
    assert restored.status_code == 200, restored.text
    assert restored.json()["user"]["id"] == ids["admin"]
    assert "acting_as" not in restored.json()


@pytest.mark.parametrize("change", ["revoked", "expired", "demoted", "actor_inactive"])
def test_member_session_never_outlives_original_admin_authority(env, change):
    c, ids = env
    result = enter(c["admin"], ids["caller"])
    with SessionLocal.begin() as db:
        child = db.get(AuthSession, decode(result["access_token"])["sid"])
        parent = db.get(AuthSession, child.parent_session_id)
        actor = db.get(User, ids["admin"])
        if change == "revoked":
            parent.revoked = True
        elif change == "expired":
            parent.expires_at = now() - timedelta(seconds=1)
        elif change == "demoted":
            actor.role = "manager"
        else:
            actor.active = False
    assert c["admin"].get("/api/leads").status_code in {401, 403}
    assert c["admin"].post("/api/auth/login-as/exit").status_code in {401, 403}


def test_logout_revokes_delegated_and_parent_session_without_logging_member_out(env):
    c, ids = env
    token = c["admin"].headers["Authorization"]
    enter(c["admin"], ids["caller"])
    assert c["admin"].post("/api/auth/logout").status_code == 200
    assert c["admin"].get("/api/leads", headers={"Authorization": token}).status_code == 401
    assert c["admin"].get("/api/leads").status_code == 401
    assert c["caller"].get("/api/leads").status_code == 200


def test_manager_login_and_owner_support_return_paths(env):
    c, ids = env
    result = enter(c["admin"], ids["manager"])
    assert result["role"] == "manager"
    assert c["admin"].get("/api/team").status_code == 200
    assert c["admin"].post(f"/api/team/{ids['caller']}/login-as").status_code == 403
    assert c["admin"].post("/api/auth/login-as/exit").status_code == 200
    support = c["owner"].post(f"/api/platform/organizations/{ids['org']}/support").json()
    c["owner"].headers["Authorization"] = "Bearer " + support["access_token"]
    delegated = enter(c["owner"], ids["caller"])
    assert delegated["support"]
    assert c["owner"].post("/api/auth/support/exit").status_code == 403
    with SessionLocal.begin() as db:
        session = db.get(AuthSession, decode(delegated["access_token"])["sid"])
        session.support_until = now() - timedelta(seconds=1)
        db.get(AuthSession, session.parent_session_id).support_until = now() - timedelta(seconds=1)
    restored = c["owner"].post("/api/auth/login-as/exit")
    assert restored.status_code == 200, restored.text
    assert restored.json()["role"] == "owner"
    assert not restored.json()["support"]


def test_target_password_reset_revokes_admin_member_login(env):
    c, ids = env
    result = enter(c["admin"], ids["caller"])
    with SessionLocal() as db:
        child = db.get(AuthSession, decode(result["access_token"])["sid"])
        parent = db.get(AuthSession, child.parent_session_id)
        from app.security import token
        original = token(parent.user_id, parent.id)
    changed = c["admin"].patch(f"/api/team/{ids['caller']}", json={"password": "UpdatedPassword!123"}, headers={"Authorization": "Bearer " + original})
    assert changed.status_code == 200
    assert c["admin"].get("/api/leads").status_code == 401
