from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.billing import today
from app.db import SessionLocal, now
from app.models import Booking, Property, SiteVisit
from conftest import make_lead


def inventory(client, reference="ORCHARD-A1204", **extra):
    payload = {
        "title": "Orchard three-bedroom residence",
        "reference": reference,
        "project": "Orchard Residences",
        "property_type": "apartment",
        "listing_type": "sale",
        "city": "Pune",
        "locality": "Baner",
        "price": "12500000.00",
        "area_sqft": "1600",
        "bedrooms": 3,
        **extra,
    }
    response = client.post("/api/properties", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def visit_payload(lead, prop, agent, offset=24):
    return {
        "lead_id": lead["id"],
        "property_id": prop["id"],
        "assignee_id": agent,
        "starts_at": (now() + timedelta(hours=offset)).isoformat(),
        "duration_minutes": 60,
    }


def booking_payload(lead, prop, agent, reference="BOOK-001"):
    return {
        "lead_id": lead["id"],
        "property_id": prop["id"],
        "agent_id": agent,
        "reference": reference,
        "agreed_price": "12000000",
        "token_amount": "100000",
        "commission": "120000",
        "booked_on": str(today()),
    }


def test_inventory_validation_isolation_and_roles(env):
    c, ids = env
    prop = inventory(c["admin"])
    assert c["caller"].get("/api/properties").json()["total"] == 1
    assert c["other"].get("/api/properties").json()["total"] == 0
    assert c["other"].get("/api/properties/" + prop["id"]).status_code == 404
    assert c["owner"].get("/api/properties").status_code == 403
    assert c["caller"].post("/api/properties", json=prop).status_code in {403, 422}
    payload = {
        k: prop[k] for k in ["title", "reference", "property_type", "listing_type", "city", "price", "area_sqft"]
    }
    assert c["caller"].post("/api/properties", json=payload).status_code == 403
    assert (
        c["admin"].post("/api/properties", json={**payload, "reference": prop["reference"].lower()}).status_code == 409
    )
    for extra in [
        {"price": "-1"},
        {"price": "0"},
        {"price": "NaN"},
        {"area_sqft": "0"},
        {"bedrooms": -1},
        {"city": " "},
        {"listing_type": "auction"},
    ]:
        assert (
            c["admin"].post("/api/properties", json={**payload, "reference": "UNIQUE-UNIT", **extra}).status_code == 422
        )
    assert c["admin"].get("/api/properties?min_price=10&max_price=1").status_code == 422
    assert (
        c["admin"]
        .get(
            "/api/properties?q=orchard&city=pune&property_type=apartment&listing_type=sale&min_price=10000000&max_price=13000000"
        )
        .json()["total"]
        == 1
    )
    assert c["admin"].get("/api/properties?max_price=0").json()["total"] == 0
    assert c["admin"].get("/api/properties?page=0").status_code == 422
    assert c["admin"].get("/api/properties?max_price=NaN").status_code == 422


@pytest.mark.parametrize(
    "kind,bedrooms,bathrooms",
    [
        ("apartment", 0, 2),
        ("villa", 0, 2),
        ("plot", None, None),
        ("office", None, 2),
        ("retail", None, 2),
        ("warehouse", None, 2),
        ("other", None, 2),
    ],
)
def test_room_counts_follow_property_type_on_create_and_edit(env, kind, bedrooms, bathrooms):
    c, _ = env
    prop = inventory(
        c["admin"], property_type=kind, bedrooms=0, bathrooms=2, rera_number="DEMO-PROJECT-REF"
    )
    assert (prop["bedrooms"], prop["bathrooms"]) == (bedrooms, bathrooms)
    assert prop["rera_number"] == "DEMO-PROJECT-REF"
    original = inventory(c["admin"], "EDIT-TYPE-001", bedrooms=3, bathrooms=2)
    payload = {
        "title": original["title"],
        "reference": original["reference"],
        "city": original["city"],
        "price": original["price"],
        "area_sqft": original["area_sqft"],
        "property_type": kind,
        "bedrooms": 0,
        "bathrooms": 2,
    }
    response = c["admin"].put("/api/properties/" + original["id"], json=payload)
    assert response.status_code == 200, response.text
    saved = c["admin"].get("/api/properties/" + original["id"]).json()
    assert (saved["bedrooms"], saved["bathrooms"]) == (bedrooms, bathrooms)
    # Even hidden fields must not bypass numeric validation through the API.
    response = c["admin"].put("/api/properties/" + original["id"], json={**payload, "bathrooms": -1})
    assert response.status_code == 422


def test_property_edit_archive_and_private_media(env):
    c, _ = env
    prop = inventory(c["manager"])
    raw = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(raw, "PNG")
    response = c["manager"].post(
        f"/api/properties/{prop['id']}/files", files={"file": ("floorplan.png", raw.getvalue(), "image/png")}
    )
    assert response.status_code == 201, response.text
    attachment = response.json()
    assert "storage_key" not in attachment
    assert c["caller"].get("/api/files/" + attachment["id"]).content == raw.getvalue()
    assert c["other"].get("/api/files/" + attachment["id"]).status_code == 404
    assert (
        c["caller"].post(f"/api/properties/{prop['id']}/files", files={"file": ("x.png", raw.getvalue())}).status_code
        == 403
    )
    assert (
        c["admin"].post(f"/api/properties/{prop['id']}/files", files={"file": ("x.png", b"not an image")}).status_code
        == 422
    )
    again = c["manager"].post(f"/api/properties/{prop['id']}/files", files={"file": ("x.png", raw.getvalue())})
    assert again.json()["id"] == attachment["id"]
    assert len(c["admin"].get("/api/properties/" + prop["id"]).json()["files"]) == 1
    assert c["manager"].delete("/api/properties/" + prop["id"]).status_code == 200
    assert c["admin"].get("/api/properties").json()["total"] == 0
    assert c["caller"].get("/api/files/" + attachment["id"]).status_code == 409
    assert c["admin"].get("/api/properties/" + prop["id"]).status_code == 409


def test_customer_brief_and_exact_property_matching(env):
    c, ids = env
    lead = make_lead(c["caller"])
    good = inventory(c["admin"])
    inventory(c["admin"], "RENT-01", listing_type="rent", price="50000")
    inventory(c["admin"], "CITY-01", city="Mumbai")
    inventory(c["admin"], "BEDS-01", bedrooms=2)
    inventory(c["admin"], "OFF-01", status="off-market")
    path = f"/api/leads/{lead['id']}/requirements"
    assert c["caller"].get(path).json() is None
    assert not c["caller"].get(f"/api/leads/{lead['id']}/property-matches").json()["criteria_saved"]
    data = {
        "purpose": "buy",
        "budget_min": "12000000",
        "budget_max": "13000000",
        "city": "Pune",
        "localities": ["baner"],
        "property_types": ["apartment"],
        "bedrooms": 3,
        "timeline": "Within 3 months",
    }
    assert c["caller"].put(path, json=data).status_code == 200
    matches = c["caller"].get(f"/api/leads/{lead['id']}/property-matches").json()["items"]
    assert [p["id"] for p in matches] == [good["id"]]
    assert c["caller2"].put(path, json=data).status_code == 404
    assert c["other"].get(path).status_code == 404
    for extra in [{"budget_max": "1"}, {"budget_min": "-1"}, {"property_types": ["unsupported"]}, {"bedrooms": -1}]:
        assert c["caller"].put(path, json={**data, **extra}).status_code == 422
    assert c["caller"].get(path).json()["budget_max"] == "13000000.00"
    c["admin"].post("/api/leads/assign", json={"lead_ids": [lead["id"]], "owner_id": ids["caller2"]})
    assert c["caller"].get(path).status_code == 404


def test_visits_clashes_reschedule_outcomes_and_scope(env):
    c, ids = env
    lead, prop = make_lead(c["caller"]), inventory(c["admin"])
    data = visit_payload(lead, prop, ids["caller"])
    response = c["caller"].post("/api/site-visits", json=data)
    assert response.status_code == 201, response.text
    visit = response.json()
    path = "/api/site-visits/" + visit["id"]
    assert c["caller"].post("/api/site-visits", json=data).status_code == 409
    assert c["caller2"].get("/api/site-visits").json()["total"] == 0
    assert c["other"].patch(path, json={"status": "cancelled"}).status_code == 404
    assert c["caller"].post("/api/site-visits", json={**data, "assignee_id": ids["caller2"]}).status_code == 403
    assert c["caller"].post("/api/site-visits", json={**data, "starts_at": "2026-01-01T10:00:00"}).status_code == 422
    assert c["caller"].post("/api/site-visits", json={**data, "starts_at": "9999-12-31T23:59:59Z"}).status_code == 422
    assert (
        c["caller"].put(path, json={**data, "starts_at": (now() + timedelta(hours=26)).isoformat()}).status_code == 200
    )
    assert c["caller"].patch(path, json={"status": "completed"}).status_code == 409
    with SessionLocal.begin() as db:
        db.get(SiteVisit, visit["id"]).starts_at = now() - timedelta(hours=1)
    assert (
        c["caller"].patch(path, json={"status": "completed", "feedback": "Buyer liked the layout"}).status_code == 200
    )
    assert c["caller"].patch(path, json={"status": "cancelled"}).status_code == 409
    assert c["caller"].put(path, json=data).status_code == 409
    assert c["caller"].get("/api/site-visits?status=completed").json()["total"] == 1


def test_visit_clash_includes_end_and_allows_touching_boundary(env):
    c, ids = env
    lead, prop = make_lead(c["admin"]), inventory(c["admin"])
    data = visit_payload(lead, prop, ids["manager"])
    assert c["admin"].post("/api/site-visits", json=data).status_code == 201
    start = now() + timedelta(hours=23, minutes=45)
    assert c["admin"].post("/api/site-visits", json={**data, "starts_at": start.isoformat()}).status_code == 409
    from datetime import datetime

    boundary = datetime.fromisoformat(data["starts_at"]) + timedelta(minutes=60)
    assert c["admin"].post("/api/site-visits", json={**data, "starts_at": boundary.isoformat()}).status_code == 201
    assert c["admin"].delete("/api/properties/" + prop["id"]).status_code == 409
    assert c["admin"].delete(f"/api/leads/{lead['id']}", params={"confirmation": lead["name"]}).status_code == 409


def test_booking_lifecycle_financial_validation_and_rental(env):
    c, ids = env
    lead, prop = make_lead(c["admin"]), inventory(c["admin"])
    data = booking_payload(lead, prop, ids["manager"])
    assert c["caller"].post("/api/bookings", json=data).status_code == 403
    for extra in [
        {"agreed_price": "0"},
        {"token_amount": "13000000"},
        {"commission": "-1"},
        {"booked_on": str(today() + timedelta(days=1))},
        {"agent_id": ids["other"]},
    ]:
        assert c["admin"].post("/api/bookings", json={**data, **extra}).status_code in {422, 404}
    response = c["manager"].post("/api/bookings", json=data)
    assert response.status_code == 201, response.text
    booking = response.json()
    path = "/api/bookings/" + booking["id"]
    assert c["admin"].get("/api/properties/" + prop["id"]).json()["status"] == "reserved"
    assert c["admin"].post("/api/bookings", json={**data, "reference": "OTHER"}).status_code == 409
    assert c["other"].patch(path, json={"status": "booked"}).status_code == 404
    assert c["admin"].patch(path, json={"status": "closed"}).status_code == 409
    assert c["admin"].patch(path, json={"status": "booked"}).status_code == 200
    assert c["admin"].patch(path, json={"status": "closed"}).status_code == 200
    assert c["admin"].get("/api/properties/" + prop["id"]).json()["status"] == "sold"
    assert c["admin"].patch(path, json={"status": "cancelled"}).status_code == 409
    assert c["admin"].get("/api/real-estate/overview").json()["commission"] == "120000.00"
    rental = inventory(c["admin"], "RENT-UNIT", listing_type="rent", price="50000")
    second = (
        c["admin"]
        .post(
            "/api/bookings",
            json={
                **booking_payload(lead, rental, ids["manager"], "LEASE-01"),
                "agreed_price": "50000",
                "token_amount": "10000",
                "commission": "10000",
            },
        )
        .json()
    )
    assert c["admin"].patch("/api/bookings/" + second["id"], json={"status": "booked"}).status_code == 200
    assert c["admin"].patch("/api/bookings/" + second["id"], json={"status": "closed"}).status_code == 200
    assert c["admin"].get("/api/properties/" + rental["id"]).json()["status"] == "leased"


def test_cancel_releases_property_and_concurrent_reservation_has_one_winner(env):
    c, ids = env
    lead, prop = make_lead(c["admin"]), inventory(c["admin"])
    data = booking_payload(lead, prop, ids["manager"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda n: c["admin"].post("/api/bookings", json={**data, "reference": f"RACE-{n}"}), range(2))
        )
    assert sorted(r.status_code for r in results) == [201, 409]
    booking = next(r.json() for r in results if r.status_code == 201)
    assert (
        c["admin"]
        .patch("/api/bookings/" + booking["id"], json={"status": "cancelled", "notes": "Buyer withdrew"})
        .status_code
        == 200
    )
    assert c["admin"].get("/api/properties/" + prop["id"]).json()["status"] == "available"
    assert c["admin"].post("/api/bookings", json={**data, "reference": "AFTER-CANCEL"}).status_code == 201


def test_lead_merge_preserves_property_briefs_visits_and_bookings(env):
    c, ids = env
    first = make_lead(c["admin"])
    second = make_lead(c["admin"], name="Duplicate buyer", phone="+919810001235")
    prop = inventory(c["admin"])
    for lead in [first, second]:
        assert (
            c["admin"]
            .put(f"/api/leads/{lead['id']}/requirements", json={"budget_max": "15000000", "notes": lead["name"]})
            .status_code
            == 200
        )
    v = c["admin"].post("/api/site-visits", json=visit_payload(second, prop, ids["manager"])).json()
    b = c["admin"].post("/api/bookings", json=booking_payload(second, prop, ids["manager"])).json()
    assert c["admin"].post(f"/api/leads/{first['id']}/merge/{second['id']}").status_code == 200
    with SessionLocal() as db:
        assert db.get(Booking, b["id"]).lead_id == first["id"]
        assert db.get(SiteVisit, v["id"]).lead_id == first["id"]
        assert db.scalar(select(Property).where(Property.id == prop["id"])).status == "reserved"
    notes = c["admin"].get(f"/api/leads/{first['id']}/history").json()["notes"]
    assert any("Property brief retained" in n["text"] for n in notes)


def test_real_estate_setup_is_repeatable_and_preserves_existing_customer_data(env):
    c, _ = env
    lead = make_lead(c["admin"], notes="Keep original customer context")
    assert c["caller"].post("/api/real-estate/setup").status_code == 403
    first = c["admin"].post("/api/real-estate/setup")
    assert first.status_code == 200
    assert first.json()["settings"]["industry"] == "real_estate"
    count = len(c["admin"].get("/api/definitions").json())
    assert c["admin"].post("/api/real-estate/setup").status_code == 200
    assert len(c["admin"].get("/api/definitions").json()) == count
    assert c["admin"].get("/api/leads/" + lead["id"]).json()["notes"] == "Keep original customer context"
