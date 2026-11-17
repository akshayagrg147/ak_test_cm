from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.message_templates import address_name, indian_price, tidy
from app.models import Lead, MessageTemplate, Note, SiteVisit
from conftest import PASSWORD, make_lead
from test_real_estate import inventory

VISIT = "{{first_name}} ji, site visit confirm: {{property_title}}, {{visit_time}}. Location bhej raha hoon."


def own_lead(c, ids, name="Rohit Sharma", phone="+919811166601", owner="caller", **values):
    lead = make_lead(c["admin"], name=name, phone=phone)
    with SessionLocal.begin() as db:
        item = db.get(Lead, lead["id"])
        item.owner_id = ids[owner]
        for key, value in values.items():
            setattr(item, key, value)
    return lead


def template(c, name="Visit confirm", body=VISIT, **extra):
    r = c["admin"].post("/api/message-templates", json={"name": name, "body": body, "purpose": "site_visit", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_template_crud_validation_roles_and_tenant(env):
    c, ids = env
    item = template(c)
    assert [t["name"] for t in c["admin"].get("/api/message-templates").json()["items"]] == ["Visit confirm"]
    dup = c["admin"].post("/api/message-templates", json={"name": "VISIT CONFIRM", "body": "Hi"})
    assert dup.status_code == 409 and "already exists" in dup.text
    bad = c["admin"].post("/api/message-templates", json={"name": "Budget", "body": "Budget {{budget}}"})
    assert bad.status_code == 422 and "{{budget}}" in bad.text
    assert c["caller"].post("/api/message-templates", json={"name": "Mine", "body": "Hi"}).status_code == 403
    assert c["manager"].put(f"/api/message-templates/{item['id']}", json={"name": "Visit confirm", "body": "Hi {{first_name}}"}).status_code == 200
    # Callers see active templates only; admins see inactive ones too.
    template(c, name="Old", body="Old text", active=False)
    assert [t["name"] for t in c["caller"].get("/api/message-templates").json()["items"]] == ["Visit confirm"]
    assert len(c["admin"].get("/api/message-templates").json()["items"]) == 2
    # Another company neither sees nor edits these.
    assert c["other"].get("/api/message-templates").json()["items"] == []
    assert c["other"].put(f"/api/message-templates/{item['id']}", json={"name": "X", "body": "Y"}).status_code == 404
    assert c["other"].delete(f"/api/message-templates/{item['id']}").status_code == 404


def test_render_fills_visit_and_property_and_tidies_blanks(env):
    c, ids = env
    lead = own_lead(c, ids)
    prop = inventory(c["admin"], reference="AR-3", title="3 BHK in Aravali Heights", locality="Sector 57", price="12500000")
    item = template(c)
    path = f"/api/leads/{lead['id']}/template-render"
    blank = c["caller"].post(path, json={"template_id": item["id"]}).json()
    assert "{{" not in blank["text"] and set(blank["missing"]) == {"property_title", "visit_time"}
    assert blank["text"].startswith("Rohit ji, site visit confirm") and ", ," not in blank["text"]
    with SessionLocal.begin() as db:
        db.add(SiteVisit(org_id=ids["org"], lead_id=lead["id"], property_id=prop["id"], assignee_id=ids["caller"],
                         creator_id=ids["admin"], starts_at=datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)))
    full = c["caller"].post(path, json={"template_id": item["id"], "property_id": prop["id"]}).json()
    assert full["missing"] == []
    assert full["text"] == "Rohit ji, site visit confirm: 3 BHK in Aravali Heights, Sat 21 Nov, 11:30 am. Location bhej raha hoon."
    details = template(c, name="Details", body="{{property_title}}, {{property_locality}}, {{property_price}}. Details: {{property_link}}")
    text = c["caller"].post(path, json={"template_id": details["id"], "property_id": prop["id"]}).json()["text"]
    assert text == "3 BHK in Aravali Heights, Sector 57, ₹1.25 Cr. Details"
    # A foreign or unavailable property, or an inactive template, cannot be used.
    other_prop = inventory(c["other"], reference="OTHER-1")
    assert c["caller"].post(path, json={"template_id": item["id"], "property_id": other_prop["id"]}).status_code == 404
    c["admin"].put(f"/api/message-templates/{item['id']}", json={"name": "Visit confirm", "body": VISIT, "active": False})
    assert c["caller"].post(path, json={"template_id": item["id"]}).status_code == 404


def test_log_says_opened_and_dnd_closed_scope_are_refused(env):
    c, ids = env
    lead = own_lead(c, ids)
    item = template(c)
    log = c["caller"].post(f"/api/leads/{lead['id']}/message-log",
                           json={"channel": "whatsapp", "template_id": item["id"], "text": "नमस्ते 🙏 Rohit ji"})
    assert log.status_code == 201, log.text
    with SessionLocal() as db:
        note = db.get(Note, log.json()["note_id"])
    assert note.text.startswith("WhatsApp message opened using template Visit confirm")
    assert "sent" not in note.text.split("\n")[0].lower() and "नमस्ते 🙏" in note.text
    # The template is referenced, so deleting hides it but keeps history.
    removed = c["admin"].delete(f"/api/message-templates/{item['id']}").json()
    assert removed["kept_for_history"] is True
    assert c["admin"].get("/api/message-templates").json()["items"] == []
    assert template(c)["name"] == "Visit confirm"  # the name is free again
    fresh = template(c, name="Unused", body="Hi {{first_name}}")
    assert c["admin"].delete(f"/api/message-templates/{fresh['id']}").json()["kept_for_history"] is False

    quiet = own_lead(c, ids, name="Quiet One", phone="+919811166602", dnd=True)
    assert c["caller"].post(f"/api/leads/{quiet['id']}/message-log", json={"channel": "sms", "text": "Hi"}).status_code == 409
    usable = template(c, name="Usable", body="Hi {{first_name}}")
    assert c["caller"].post(f"/api/leads/{quiet['id']}/template-render", json={"template_id": usable["id"]}).status_code == 409
    # Won/lost clients stay messageable (owner's decision); archived ones are not found.
    closed = own_lead(c, ids, name="Closed One", phone="+919811166603", stage="lost", status="lost")
    assert c["caller"].post(f"/api/leads/{closed['id']}/template-render", json={"template_id": usable["id"]}).status_code == 200
    archived = own_lead(c, ids, name="Archived One", phone="+919811166605", deleted=True)
    assert c["caller"].post(f"/api/leads/{archived['id']}/message-log", json={"channel": "sms", "text": "Hi"}).status_code == 404
    others = own_lead(c, ids, name="Not Mine", phone="+919811166604", owner="caller2")
    assert c["caller"].post(f"/api/leads/{others['id']}/template-render", json={"template_id": item["id"]}).status_code == 404
    assert c["other"].post(f"/api/leads/{lead['id']}/message-log", json={"channel": "sms", "text": "Hi"}).status_code == 404
    assert c["caller"].post(f"/api/leads/{lead['id']}/message-log", json={"channel": "whatsapp", "text": "x" * 1001}).status_code == 422


def test_new_real_estate_company_gets_starters_once(env):
    c, ids = env
    payload = {
        "name": "Evergreen Realty", "industry": "real_estate", "brand_name": "Evergreen",
        "admin": {"name": "Evergreen Admin", "phone": "+919900006001", "password": PASSWORD, "role": "admin"},
    }
    org = c["owner"].post("/api/platform/organizations", json=payload).json()["organization"]
    admin = TestClient(app)
    token = admin.post("/api/auth/login", json={"phone": "+919900006001", "password": PASSWORD}).json()["access_token"]
    admin.headers.update({"Authorization": "Bearer " + token, "X-Requested-With": "TalkoCRM"})
    names = [t["name"] for t in admin.get("/api/message-templates").json()["items"]]
    assert names == ["Introduction", "Site visit confirm", "Call not answered", "Property details"]
    first = admin.get("/api/message-templates").json()["items"][0]
    admin.put(f"/api/message-templates/{first['id']}", json={"name": "Introduction", "body": "Edited {{first_name}}"})
    assert admin.post("/api/real-estate/setup").status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MessageTemplate).where(MessageTemplate.org_id == org["id"])) == 4
        assert db.scalar(select(MessageTemplate.body).where(MessageTemplate.id == first["id"])) == "Edited {{first_name}}"
    # An existing company enabling real estate gets them once too.
    assert c["admin"].post("/api/real-estate/setup").status_code == 200
    assert c["admin"].post("/api/real-estate/setup").status_code == 200
    assert len(c["admin"].get("/api/message-templates").json()["items"]) == 4
    admin.close()


def test_price_and_tidy_helpers():
    assert indian_price(Decimal("12500000")) == "₹1.25 Cr"
    assert indian_price(Decimal("8500000")) == "₹85 L"
    assert indian_price(Decimal("25000")) == "₹25,000"
    assert indian_price(Decimal("850")) == "₹850"
    assert tidy("Rohit ji, site visit confirm: , . Location") == "Rohit ji, site visit confirm. Location"
    assert address_name("Mr. Rohit Sharma") == "Rohit" and address_name("Smt Kavita") == "Kavita"
    assert address_name("Dr.") == "Dr." and address_name("") == ""


def test_qa_fixes_clamp_removed_templates_seed_once_errors_and_partial_edit(env):
    c, ids = env
    lead = own_lead(c, ids, name="R" + "a" * 150)
    long = template(c, name="Long", body="{{client_name}} " * 60)
    rendered = c["caller"].post(f"/api/leads/{lead['id']}/template-render", json={"template_id": long["id"]}).json()
    assert rendered["truncated"] is True and len(rendered["text"]) <= 1000
    logged = c["caller"].post(f"/api/leads/{lead['id']}/message-log",
                              json={"channel": "whatsapp", "template_id": long["id"], "text": rendered["text"]})
    assert logged.status_code == 201, logged.text
    # Inactive or deleted templates cannot be named in a log.
    paused = template(c, name="Paused", body="Hi {{first_name}}", active=False)
    assert c["caller"].post(f"/api/leads/{lead['id']}/message-log",
                            json={"channel": "sms", "template_id": paused["id"], "text": "Hi"}).status_code == 404
    gone = template(c, name="Gone", body="Hi")
    assert c["admin"].delete(f"/api/message-templates/{gone['id']}").json()["kept_for_history"] is False
    assert c["caller"].post(f"/api/leads/{lead['id']}/message-log",
                            json={"channel": "sms", "template_id": gone["id"], "text": "Hi"}).status_code == 404
    # A clean placeholder error, without the field path prefix.
    bad = c["admin"].post("/api/message-templates", json={"name": "Budget", "body": "Budget {{budget}}"}).json()
    assert bad["error"]["message"].startswith("Unknown placeholder {{budget}}")
    # A partial edit keeps the saved purpose.
    edited = c["admin"].put(f"/api/message-templates/{long['id']}", json={"name": "Long text"}).json()
    assert edited["name"] == "Long text" and edited["purpose"] == "site_visit"
    assert c["admin"].put(f"/api/message-templates/{long['id']}", json={"purpose": None}).status_code == 422
    # Starter templates are added once: deleting them all and re-running setup keeps them gone.
    c["admin"].post("/api/real-estate/setup")
    for item in c["admin"].get("/api/message-templates").json()["items"]:
        c["admin"].delete(f"/api/message-templates/{item['id']}")
    assert c["admin"].post("/api/real-estate/setup").status_code == 200
    assert c["admin"].get("/api/message-templates").json()["items"] == []
