import os
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://127.0.0.1:55432/talkocrm_test")
os.environ["ENVIRONMENT"] = "test"
os.environ["STORAGE_PATH"] = str(Path(__file__).resolve().parents[2] / ".local" / "test-storage")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.common import init_org
from app.db import SessionLocal, engine
from app.main import app
from app.models import Organization, User
from app.security import passwords

PASSWORD = "TestPassword!123"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    if not engine.url.database.endswith("_test"):
        raise RuntimeError("Tests require a dedicated database ending in _test")
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture()
def env(migrated_database):
    from app.db import Base

    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE " + ", ".join('"' + table.name + '"' for table in Base.metadata.sorted_tables) + " CASCADE")
        )
    clients, ids = {}, {}
    with SessionLocal.begin() as db:
        org = Organization(
            name="Test Organization",
            settings={
                "weekdays": [0, 1, 2, 3, 4],
                "daily_hours": "8",
                "workplace": {
                    "name": "Office",
                    "latitude": 19.076,
                    "longitude": 72.8777,
                    "radius": 200,
                    "accuracy": 0,
                    "timezone": "Asia/Kolkata",
                },
            },
        )
        other = Organization(name="Other Organization")
        db.add_all([org, other])
        db.flush()
        ids.update(org=org.id, other_org=other.id)
        init_org(db, org)
        init_org(db, other)
        hash_value = passwords.hash(PASSWORD)
        for index, (name, role, org_id) in enumerate(
            [
                ("owner", "owner", None),
                ("admin", "admin", org.id),
                ("manager", "manager", org.id),
                ("caller", "telecaller", org.id),
                ("caller2", "telecaller", org.id),
                ("other", "admin", other.id),
            ]
        ):
            user = User(
                name=name.title() + " User",
                role=role,
                org_id=org_id,
                phone=f"+91990000100{index}",
                password_hash=hash_value,
            )
            db.add(user)
            db.flush()
            ids[name] = user.id
    for index, name in enumerate(["owner", "admin", "manager", "caller", "caller2", "other"]):
        c = TestClient(app)
        r = c.post("/api/auth/login", json={"phone": f"+91990000100{index}", "password": PASSWORD})
        assert r.status_code == 200, r.text
        c.headers.update({"Authorization": "Bearer " + r.json()["access_token"], "X-Requested-With": "TalkoCRM"})
        clients[name] = c
    yield clients, ids
    for c in clients.values():
        c.close()


def make_lead(client, name="Example Customer", phone="+919810001234", **kwargs):
    r = client.post("/api/leads", json={"name": name, "phone": phone, **kwargs})
    assert r.status_code == 201, r.text
    return r.json()
