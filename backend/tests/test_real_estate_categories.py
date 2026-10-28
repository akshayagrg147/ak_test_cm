from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Definition, Organization
from conftest import PASSWORD, make_lead


PROPERTY_CATEGORIES = {"apartment", "villa", "plot", "office", "retail", "warehouse", "other"}
HEALTHCARE_CATEGORIES = {"pharmaceutical", "ayurvedic", "homeopathic", "nutraceutical", "generic"}


def active_categories(client):
    return {d["key"] for d in client.get("/api/definitions").json() if d["kind"] == "category" and d["active"]}


def test_conversion_retires_old_defaults_but_preserves_custom_categories_and_history(env):
    clients, _ = env
    admin = clients["admin"]
    old = make_lead(admin, category="ayurvedic", interests=["Old confirmed interest"], notes="Keep customer context")
    saved = admin.post(
        "/api/saved-views", json={"name": "Previous category", "kind": "leads", "filters": {"category": "ayurvedic"}}
    )
    assert saved.status_code == 201
    assert (
        admin.post("/api/definitions", json={"kind": "category", "key": "farmhouse", "label": "Farmhouse"}).status_code
        == 201
    )
    # A user-renamed seed is custom data, so conversion must not retire it.
    seed = next(
        d for d in admin.get("/api/definitions").json() if d["kind"] == "category" and d["key"] == "pharmaceutical"
    )
    assert (
        admin.put(
            "/api/definitions/" + seed["id"],
            json={**{k: seed[k] for k in ["kind", "key", "position", "active", "config"]}, "label": "Medical offices"},
        ).status_code
        == 200
    )
    assert admin.post("/api/real-estate/setup").status_code == 200
    assert active_categories(admin) == PROPERTY_CATEGORIES | {"farmhouse", "pharmaceutical"}
    assert HEALTHCARE_CATEGORIES <= active_categories(clients["other"])
    before = admin.get("/api/definitions").json()
    assert admin.post("/api/real-estate/setup").status_code == 200
    assert admin.get("/api/definitions").json() == before
    detail = admin.get("/api/leads/" + old["id"]).json()
    assert detail["category"] == "ayurvedic"
    assert detail["interests"] == ["Old confirmed interest"]
    assert detail["notes"] == "Keep customer context"
    assert admin.patch("/api/leads/" + old["id"], json={"notes": "Updated without changing history"}).status_code == 200
    assert admin.get("/api/leads?category=ayurvedic").json()["total"] == 1
    assert admin.get("/api/saved-views").json()[0]["filters"] == {"category": "ayurvedic"}
    rejected = admin.post("/api/leads", json={"name": "New buyer", "phone": "9810009998", "category": "ayurvedic"})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "invalid_category"
    assert make_lead(admin, name="Property buyer", phone="9810009999", category="apartment")["category"] == "apartment"


def test_new_real_estate_company_starts_with_only_property_categories(env):
    clients, _ = env
    response = clients["owner"].post(
        "/api/platform/organizations",
        json={
            "name": "Category regression company",
            "industry": "real_estate",
            "admin": {"name": "Estate Admin", "phone": "+919900008001", "password": PASSWORD, "role": "admin"},
        },
    )
    assert response.status_code == 201, response.text
    with TestClient(app) as admin:
        signed = admin.post("/api/auth/login", json={"phone": "+919900008001", "password": PASSWORD})
        assert signed.status_code == 200
        admin.headers.update(
            {"Authorization": "Bearer " + signed.json()["access_token"], "X-Requested-With": "TalkoCRM"}
        )
        assert active_categories(admin) == PROPERTY_CATEGORIES


def test_real_estate_settings_cannot_restore_pharma_qualification_fields(env):
    clients, _ = env
    assert clients["admin"].post("/api/real-estate/setup").status_code == 200
    response = clients["admin"].put("/api/settings", json={"pharma_enabled": True})
    assert response.status_code == 200
    assert response.json()["settings"]["industry"] == "real_estate"
    assert response.json()["settings"]["pharma_enabled"] is False
    assert (
        clients["other"].put("/api/settings", json={"pharma_enabled": True}).json()["settings"]["pharma_enabled"]
        is True
    )


def test_backfill_repairs_already_converted_companies_without_touching_custom_or_general_data(env):
    clients, ids = env
    command.downgrade(Config("alembic.ini"), "0004")
    old = make_lead(clients["admin"], category="ayurvedic", notes="Do not rewrite me")
    with SessionLocal.begin() as db:
        org = db.get(Organization, ids["org"])
        org.settings = {**org.settings, "industry": "real_estate", "pharma_enabled": True}
        seed = db.scalar(
            select(Definition).where(
                Definition.org_id == org.id, Definition.kind == "category", Definition.key == "pharmaceutical"
            )
        )
        seed.label = "Medical offices"
        db.add(Definition(org_id=org.id, kind="category", key="farmhouse", label="Farmhouse"))
    command.upgrade(Config("alembic.ini"), "head")
    assert active_categories(clients["admin"]) == {"other", "pharmaceutical", "farmhouse"}
    assert HEALTHCARE_CATEGORIES <= active_categories(clients["other"])
    assert clients["admin"].get("/api/settings").json()["settings"]["pharma_enabled"] is False
    assert clients["admin"].get("/api/leads/" + old["id"]).json()["notes"] == "Do not rewrite me"
    assert clients["admin"].get("/api/leads/" + old["id"]).json()["category"] == "ayurvedic"
    # A schema downgrade must not reactivate retired company categories.
    command.downgrade(Config("alembic.ini"), "0004")
    assert "ayurvedic" not in active_categories(clients["admin"])
    command.upgrade(Config("alembic.ini"), "head")
