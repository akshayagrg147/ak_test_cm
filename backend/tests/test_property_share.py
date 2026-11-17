import io
import re

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Lead, Property, PropertyShare
from conftest import make_lead
from test_real_estate import inventory

ALLOWED = {"company", "contact", "available", "title", "price", "listing_type", "property_type", "bedrooms",
           "bathrooms", "area_sqft", "locality", "city", "possession", "amenities", "description", "rera_number",
           "photos", "documents"}


def image(color):
    raw = io.BytesIO()
    Image.new("RGB", (2400, 1800), color).save(raw, "PNG")
    return raw.getvalue()


def pdf():
    raw = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(raw, "PDF")
    return raw.getvalue()


def setup_property(c, **extra):
    prop = inventory(c["admin"], reference="SHARE-P1", title="3 BHK in Aravali Heights", locality="Sector 57",
                     city="Gurugram", price="12500000", address="Tower B, Flat 1204, Secret Lane",
                     developer="Owner Mr. Private", rera_number="RERA-GGM-123", **extra)
    files = []
    for n, color in enumerate(["red", "green", "blue", "yellow", "purple"]):
        r = c["admin"].post(f"/api/properties/{prop['id']}/files", files={"file": (f"photo{n}.png", image(color), "image/png")})
        assert r.status_code == 201, r.text
        files.append(r.json())
    r = c["admin"].post(f"/api/properties/{prop['id']}/files", files={"file": ("brochure.pdf", pdf(), "application/pdf")})
    assert r.status_code == 201, r.text
    return prop, files, r.json()


def anonymous(ip):
    client = TestClient(app)
    client.headers.update({"X-Forwarded-For": ip})
    return client


def token_of(url):
    return url.rsplit("/p/", 1)[1]


def test_public_page_allow_list_photos_replace_and_disable(env):
    c, ids = env
    prop, photos, brochure = setup_property(c)
    shared = c["admin"].put(f"/api/properties/{prop['id']}/share", json={}).json()
    assert shared["enabled"] and len(token_of(shared["url"])) >= 22 and prop["id"] not in shared["url"]
    token = token_of(shared["url"])
    web = anonymous("203.0.113.10")
    body = web.get(f"/api/public/p/{token}").json()
    assert set(body) <= ALLOWED
    text = str(body)
    for secret in [prop["id"], "SHARE-P1", "Secret Lane", "Owner Mr. Private", photos[0]["id"], brochure["id"], "storage"]:
        assert secret not in text, secret
    assert body["title"] == "3 BHK in Aravali Heights" and body["price"] == "₹1.25 Cr" and len(body["photos"]) == 5
    assert body["documents"] == [] and body["rera_number"] == "RERA-GGM-123"
    page = web.get(f"/p/{token}")
    assert page.status_code == 200 and "noindex" in page.headers["x-robots-tag"]
    assert page.headers["referrer-policy"] == "no-referrer"
    assert "og:title" in page.text and "og:image" in page.text and "<script" not in page.text
    assert "Secret Lane" not in page.text and "SHARE-P1" not in page.text
    assert "Call Admin User" in page.text and "wa.me/91990000100" in page.text
    photo = web.get(f"/api/public/p/{token}/photo/0")
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(photo.content)).size) <= 1600
    assert c["admin"].get(f"/api/properties/{prop['id']}/share").json()["views"] == 1

    # A ticked subset of 2 of 5 photos; the unticked PDF is never public.
    c["admin"].put(f"/api/properties/{prop['id']}/share", json={"photo_file_ids": [photos[1]["id"], photos[3]["id"]]})
    assert len(web.get(f"/api/public/p/{token}").json()["photos"]) == 2
    assert web.get(f"/api/public/p/{token}/photo/1").status_code == 200
    assert web.get(f"/api/public/p/{token}/photo/3").status_code == 404
    assert web.get(f"/api/public/p/{token}/doc/0").status_code == 404
    c["admin"].put(f"/api/properties/{prop['id']}/share", json={"doc_file_ids": [brochure["id"]], "show_rera": False})
    assert web.get(f"/api/public/p/{token}/doc/0").content.startswith(b"%PDF")
    assert web.get(f"/api/public/p/{token}").json()["rera_number"] == ""

    # Replace: the old token stops at once; turning off looks exactly like a random token.
    new = token_of(c["admin"].post(f"/api/properties/{prop['id']}/share/replace").json()["url"])
    assert web.get(f"/p/{token}").status_code == 404 and web.get(f"/p/{new}").status_code == 200
    assert c["admin"].delete(f"/api/properties/{prop['id']}/share").json()["enabled"] is False
    off, random = web.get(f"/p/{new}"), web.get("/p/" + "x" * 22)
    assert off.status_code == random.status_code == 404 and off.text == random.text
    assert web.get(f"/api/public/p/{new}").status_code == 404


def test_sold_property_shows_contact_only_and_suspended_company_404(env):
    c, ids = env
    prop, photos, _ = setup_property(c)
    token = token_of(c["admin"].put(f"/api/properties/{prop['id']}/share", json={}).json()["url"])
    web = anonymous("203.0.113.20")
    with SessionLocal.begin() as db:
        db.get(Property, prop["id"]).status = "sold"
    page = web.get(f"/p/{token}")
    assert page.status_code == 200 and "no longer available" in page.text and "Call Admin User" in page.text
    assert "/photo/" not in page.text and "Aravali" in page.text  # title only in the "similar options" text
    assert web.get(f"/api/public/p/{token}/photo/0").status_code == 404
    assert set(web.get(f"/api/public/p/{token}").json()) == {"company", "contact", "available"}
    from app.models import Organization
    with SessionLocal.begin() as db:
        db.get(Organization, ids["org"]).active = False
    assert web.get(f"/p/{token}").status_code == 404


def test_roles_tenant_dnd_and_rate_limit(env):
    c, ids = env
    prop, _, _ = setup_property(c)
    path = f"/api/properties/{prop['id']}/share"
    assert c["caller"].put(path, json={}).status_code == 403
    assert c["other"].get(path).status_code == 404
    assert c["other"].put(path, json={}).status_code == 404
    assert c["admin"].put("/api/property-share-settings", json={"callers_can_share": True}).status_code == 200
    assert c["caller"].put("/api/property-share-settings", json={"callers_can_share": False}).status_code == 403
    assert c["caller"].put(path, json={}).status_code == 200
    url = c["caller"].get(path).json()["url"]
    # Lead-page share: logged as "opened", refused for DND, and the link reaches templates and matches.
    lead = make_lead(c["admin"], name="Share Buyer", phone="+919811177701")
    quiet = make_lead(c["admin"], name="Quiet Buyer", phone="+919811177702", dnd=True)
    with SessionLocal.begin() as db:
        for item in (lead, quiet):
            db.get(Lead, item["id"]).owner_id = ids["caller"]
    ok = c["caller"].post(f"/api/leads/{lead['id']}/property-share-log", json={"property_id": prop["id"]})
    assert ok.status_code == 201 and ok.json()["url"] == url
    assert c["caller"].post(f"/api/leads/{quiet['id']}/property-share-log", json={"property_id": prop["id"]}).status_code == 409
    history = str(c["caller"].get(f"/api/leads/{lead['id']}/history").json())
    assert "Shared property 3 BHK in Aravali Heights link on WhatsApp (opened)" in history
    c["caller"].put(f"/api/leads/{lead['id']}/requirements", json={"purpose": "buy", "budget_min": "0"})
    matches = c["caller"].get(f"/api/leads/{lead['id']}/property-matches").json()["items"]
    assert matches[0]["share_url"] == url
    tpl = c["admin"].post("/api/message-templates", json={"name": "Link", "body": "Details: {{property_link}}"}).json()
    rendered = c["caller"].post(f"/api/leads/{lead['id']}/template-render", json={"template_id": tpl["id"], "property_id": prop["id"]}).json()
    assert rendered["text"] == "Details: " + url
    # 100 requests in a minute from one visitor are rate-limited; another visitor is unaffected.
    token = token_of(url)
    burst = anonymous("198.51.100.7")
    codes = [burst.get(f"/api/public/p/{token}").status_code for _ in range(100)]
    assert codes[:60] == [200] * 60 and set(codes[60:]) == {429}
    assert anonymous("198.51.100.8").get(f"/api/public/p/{token}").status_code == 200
    with SessionLocal() as db:
        stored = db.scalar(select(PropertyShare))
        assert token not in stored.token_enc and re.fullmatch(r"[0-9a-f]{64}", stored.token_hash)
