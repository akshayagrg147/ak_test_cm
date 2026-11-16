from sqlalchemy import select

from app.db import SessionLocal
from app.models import Audit, Lead
from conftest import make_lead


def test_whatsapp_open_is_logged_as_opened_never_sent(env):
    c, ids = env
    lead = make_lead(c["admin"], name="Chat Buyer", phone="+919811155501")
    with SessionLocal.begin() as db:
        db.get(Lead, lead["id"]).owner_id = ids["caller"]
    r = c["caller"].post(f"/api/leads/{lead['id']}/whatsapp-opened", json={})
    assert r.status_code == 201, r.text
    with SessionLocal() as db:
        entry = db.scalar(select(Audit).where(Audit.entity_id == lead["id"], Audit.action == "whatsapp_opened"))
    assert entry is not None and entry.actor_id == ids["caller"]
    assert entry.summary == "Opened a WhatsApp chat (click-to-chat)" and "sent" not in entry.summary.lower()
    history = c["caller"].get(f"/api/leads/{lead['id']}/history").json()
    assert "Opened a WhatsApp chat" in str(history)


def test_whatsapp_open_respects_dnd_scope_and_tenant(env):
    c, ids = env
    quiet = make_lead(c["admin"], name="Quiet Buyer", phone="+919811155502", dnd=True)
    assert c["admin"].post(f"/api/leads/{quiet['id']}/whatsapp-opened", json={}).status_code == 409
    other = make_lead(c["admin"], name="Someone Else's Buyer", phone="+919811155503")
    with SessionLocal.begin() as db:
        db.get(Lead, other["id"]).owner_id = ids["caller2"]
    assert c["caller"].post(f"/api/leads/{other['id']}/whatsapp-opened", json={}).status_code == 404
    assert c["other"].post(f"/api/leads/{other['id']}/whatsapp-opened", json={}).status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(Audit).where(Audit.action == "whatsapp_opened")) is None
