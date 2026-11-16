import itertools
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.matching import requirement_matches
from app.models import BuyerRequirement, Lead, Property
from conftest import make_lead
from test_real_estate import inventory

P = {
    "reference": "SEC57-3BHK",
    "city": "Gurugram",
    "locality": "Sector 57",
    "property_type": "apartment",
    "listing_type": "sale",
    "bedrooms": 3,
    "price": "12000000",
}
WANT = {"purpose": "buy", "budget_min": "10000000", "budget_max": "15000000", "city": "gurugram",
        "localities": [" sector 57 "], "property_types": ["apartment"], "bedrooms": 3}


def buyer(client, name, phone, requirement=WANT, owner=None, **lead):
    created = make_lead(client, name=name, phone=phone, **lead)
    if owner:
        set_lead(created["id"], owner_id=owner)
    r = client.put(f"/api/leads/{created['id']}/requirements", json=requirement)
    assert r.status_code == 200, r.text
    return created


def set_lead(lead_id, **values):
    with SessionLocal.begin() as db:
        item = db.get(Lead, lead_id)
        for key, value in values.items():
            setattr(item, key, value)


def test_reverse_match_rules_dnd_closed_and_create_message(env):
    c, ids = env
    admin = c["admin"]
    l1 = buyer(admin, "L1 Match", "+919811100001")
    buyer(admin, "L2 Low budget", "+919811100002", {**WANT, "budget_max": "10000000"})
    buyer(admin, "L3 Rent", "+919811100003", {**WANT, "purpose": "rent"})
    l4 = buyer(admin, "L4 DND", "+919811100004")
    l5 = buyer(admin, "L5 Lost", "+919811100005")
    set_lead(l4["id"], dnd=True)
    set_lead(l5["id"], stage="lost", status="lost")

    created = inventory(admin, **P)
    assert "buyer_match_count" not in created  # create/edit payloads keep their shape for round-trips
    body = admin.get(f"/api/properties/{created['id']}/buyer-matches").json()
    assert body["available"] is True
    assert [item["name"] for item in body["items"]] == ["L1 Match"]
    assert body["total"] == 1 and body["dnd_hidden"] == 1
    assert "L4 DND" not in str(body)  # DND buyers appear only as a count
    assert body["items"][0]["localities"] == ["sector 57"] and body["items"][0]["id"] == l1["id"]

    listed = admin.get("/api/properties").json()["items"]
    assert next(p for p in listed if p["id"] == created["id"])["buyer_match_count"] == 1

    # Reserved or sold inventory shows nothing.
    with SessionLocal.begin() as db:
        db.get(Property, created["id"]).status = "reserved"
    gone = admin.get(f"/api/properties/{created['id']}/buyer-matches").json()
    assert gone == {"items": [], "total": 0, "dnd_hidden": 0, "available": False, "page": 1}
    assert next(p for p in admin.get("/api/properties").json()["items"] if p["id"] == created["id"])["buyer_match_count"] is None


def test_reverse_match_is_scoped_to_role_and_tenant(env):
    c, ids = env
    admin = c["admin"]
    l1 = buyer(admin, "Caller one buyer", "+919811100011", owner=ids["caller"])
    l6 = buyer(admin, "Caller two buyer", "+919811100016", owner=ids["caller2"])
    prop = inventory(admin, **P)
    path = f"/api/properties/{prop['id']}/buyer-matches"
    t1, t2 = c["caller"].get(path).json(), c["caller2"].get(path).json()
    assert [i["id"] for i in t1["items"]] == [l1["id"]] and t1["total"] == 1
    assert [i["id"] for i in t2["items"]] == [l6["id"]] and t2["total"] == 1
    assert admin.get(path).json()["total"] == 2
    # Badge counts equal endpoint totals for each role.
    for role in ["admin", "manager", "caller", "caller2"]:
        badge = next(p for p in c[role].get("/api/properties").json()["items"] if p["id"] == prop["id"])
        assert badge["buyer_match_count"] == c[role].get(path).json()["total"], role
    # DND is also counted only within the caller's own scope.
    set_lead(l6["id"], dnd=True)
    assert c["caller"].get(path).json()["dnd_hidden"] == 0
    assert c["caller2"].get(path).json()["dnd_hidden"] == 1
    # Another company cannot read this property's buyers.
    assert c["other"].get(path).status_code == 404
    assert c["owner"].get(path).status_code in (403, 404)


def test_forward_and_reverse_matches_agree_on_a_10_by_10_grid(env):
    c, ids = env
    admin = c["admin"]
    cities, localities = ["Gurugram", "Noida"], ["Sector 57", "Sector 150", "Golf Course Road"]
    props = []
    for i in range(10):
        props.append(inventory(
            admin,
            reference=f"GRID-{i}",
            city=cities[i % 2],
            locality=localities[i % 3],
            property_type=["apartment", "villa", "plot"][i % 3] if i % 3 != 2 else "plot",
            listing_type="rent" if i == 9 else "sale",
            bedrooms=None if i % 3 == 2 else 2 + i % 3,
            price=str(8000000 + i * 1500000) if i != 9 else "45000",
            area_sqft="1200",
        ))
    requirements = [
        {"purpose": "buy", "budget_min": "0"},
        {"purpose": "buy", "budget_min": "9000000", "budget_max": "16000000"},
        {"purpose": "invest", "budget_min": "0", "city": " NOIDA "},
        {"purpose": "buy", "budget_min": "0", "localities": ["sector 57", "GOLF COURSE ROAD "]},
        {"purpose": "buy", "budget_min": "0", "property_types": ["villa"]},
        {"purpose": "buy", "budget_min": "0", "bedrooms": 3},
        {"purpose": "rent", "budget_min": "0", "budget_max": "50000"},
        {"purpose": "buy", "budget_min": "20000000"},
        {"purpose": "buy", "budget_min": "0", "city": "Gurugram", "property_types": ["plot"]},
        {"purpose": "buy", "budget_min": "10000000", "budget_max": "10000000"},
    ]
    leads = [buyer(admin, f"Grid buyer {i}", f"+91981120{i:04}", r) for i, r in enumerate(requirements)]
    forward = {
        (lead["id"], p["id"])
        for lead in leads
        for p in admin.get(f"/api/leads/{lead['id']}/property-matches").json()["items"]
    }
    reverse = {
        (item["id"], p["id"])
        for p in props
        for item in admin.get(f"/api/properties/{p['id']}/buyer-matches").json()["items"]
    }
    with SessionLocal() as db:
        reqs = {r.lead_id: r for r in db.scalars(select(BuyerRequirement))}
        prop_rows = {p.id: p for p in db.scalars(select(Property))}
        python = {
            (lead["id"], p["id"])
            for lead, p in itertools.product(leads, props)
            if requirement_matches(reqs[lead["id"]], prop_rows[p["id"]])
        }
    assert forward == reverse == python
    assert 10 <= len(forward) < 100  # the grid exercises both matches and non-matches
    assert prop_rows[props[0]["id"]].price == Decimal("8000000")
