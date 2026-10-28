import csv
import io

import pytest

from app.common import score
from app.db import SessionLocal
from app.models import Lead
from conftest import make_lead


@pytest.mark.parametrize("pharma", [False, True])
@pytest.mark.parametrize("role", ["admin", "manager", "caller"])
def test_interests_available_to_every_business_and_role_and_clearable(env, pharma, role):
    clients, _ = env
    assert clients["admin"].put("/api/settings", json={"pharma_enabled": pharma}).status_code == 200
    lead = make_lead(clients[role])
    assert lead["score"]["value"] == 20
    assert lead["score"]["factors"]["Interests recorded"] == 0
    path = "/api/leads/" + lead["id"]
    r = clients[role].patch(path, json={"interests": [" Inventory setup ", "Support", "inventory SETUP"]})
    assert r.status_code == 200, r.text
    assert r.json()["interests"] == ["Inventory setup", "Support"]
    assert r.json()["score"]["value"] == 35
    assert r.json()["score"]["factors"]["Interests recorded"] == 15
    # An unrelated edit preserves interests; reading a new request proves persistence.
    assert clients[role].patch(path, json={"city": "Pune"}).status_code == 200
    persisted = clients[role].get(path).json()
    assert persisted["interests"] == ["Inventory setup", "Support"]
    assert persisted["score"]["value"] == 45 and persisted["score"]["band"] == "warm"
    cleared = clients[role].patch(path, json={"interests": []})
    assert cleared.status_code == 200
    assert clients[role].get(path).json()["interests"] == []
    assert cleared.json()["score"]["value"] == 30
    assert cleared.json()["score"]["factors"]["Interests recorded"] == 0


@pytest.mark.parametrize(
    "interests", [None, "CRM", [""], ["  "], ["x" * 161], ["A"] * 31, ["A|B"], ["A\nB"], ["A\x00B"], [123], [{}]]
)
def test_invalid_interests_fail_without_persisting_or_changing_score(env, interests):
    clients, _ = env
    client = clients["admin"]
    lead = make_lead(client, interests=["Support"])
    created = client.post(
        "/api/leads", json={"name": "Invalid interests", "phone": "9810001235", "interests": interests}
    )
    assert created.status_code == 422, created.text
    path = "/api/leads/" + lead["id"]
    edited = client.patch(path, json={"interests": interests})
    assert edited.status_code == 422, edited.text
    assert client.get(path).json()["interests"] == ["Support"]
    assert client.get(path).json()["score"]["value"] == 35
    assert client.get("/api/leads").json()["total"] == 1


def test_interests_authorization_and_primary_category_remain_separate(env):
    clients, _ = env
    lead = make_lead(clients["caller"], interests=["CRM implementation"])
    path = "/api/leads/" + lead["id"]
    for role in ["caller2", "other"]:
        assert clients[role].patch(path, json={"interests": ["Forged change"]}).status_code == 404
    assert clients["caller"].get(path).json()["interests"] == ["CRM implementation"]
    r = clients["caller"].patch(path, json={"category": "Not a configured category"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_category"


def test_import_template_preview_commit_and_export_keep_product_interests(env):
    clients, _ = env
    client = clients["caller"]
    assert "interests" in client.get("/api/imports/template").text.splitlines()[0]
    content = "name,phone,interests\nInterest Customer,9810001234,CRM setup|Support|उत्पाद|crm SETUP\n"
    for commit in [False, True]:
        r = client.post(
            "/api/imports?commit=" + str(commit).lower(), files={"file": ("interests.csv", content.encode())}
        )
        assert r.status_code == 200, r.text
        assert r.json()["invalid"] == 0
    lead = client.get("/api/leads").json()["items"][0]
    assert lead["interests"] == ["CRM setup", "Support", "उत्पाद"]
    assert lead["score"]["factors"]["Interests recorded"] == 15
    export = client.get("/api/leads/export")
    exported = list(csv.DictReader(io.StringIO(export.text.lstrip("\ufeff"))))
    assert exported[0]["interests"] == "CRM setup|Support|उत्पाद"
    assert client.patch("/api/leads/" + lead["id"], json={"interests": ["=1+1"]}).status_code == 200
    safe = list(csv.DictReader(io.StringIO(client.get("/api/leads/export").text.lstrip("\ufeff"))))
    assert safe[0]["interests"] == "'=1+1"


def test_existing_category_interests_survive_and_merge_with_new_product_interests(env):
    clients, _ = env
    client = clients["admin"]
    primary = make_lead(client, interests=["generic", "CRM setup"])
    duplicate = make_lead(client, phone="9810001235", interests=["Generic", "Support"])
    r = client.post(f"/api/leads/{primary['id']}/merge/{duplicate['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["interests"] == ["generic", "CRM setup", "Support"]
    assert r.json()["score"]["factors"]["Interests recorded"] == 15
    assert client.get("/api/leads/" + duplicate["id"]).status_code == 404


def test_interest_merge_limit_preserves_both_leads_and_their_history(env):
    clients, _ = env
    client = clients["admin"]
    primary = make_lead(client, interests=["Product " + str(i) for i in range(30)])
    duplicate = make_lead(client, phone="9810001235", interests=["One more"])
    assert client.post(f"/api/leads/{duplicate['id']}/notes", json={"text": "Keep this context"}).status_code == 201
    r = client.post(f"/api/leads/{primary['id']}/merge/{duplicate['id']}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_many_interests"
    assert client.get("/api/leads/" + primary["id"]).json()["interests"] == primary["interests"]
    assert client.get("/api/leads/" + duplicate["id"]).json()["interests"] == ["One more"]
    assert client.get(f"/api/leads/{duplicate['id']}/history").json()["notes"][0]["text"] == "Keep this context"
    assert client.get(f"/api/leads/{primary['id']}/history").json()["notes"] == []


def test_legacy_blank_interests_do_not_award_points(env):
    clients, _ = env
    lead = make_lead(clients["admin"])
    with SessionLocal.begin() as db:
        old = db.get(Lead, lead["id"])
        old.interests = ["", " "]
        assert score(old)["factors"]["Interests recorded"] == 0
    assert clients["admin"].get("/api/leads/" + lead["id"]).json()["score"]["value"] == 20
