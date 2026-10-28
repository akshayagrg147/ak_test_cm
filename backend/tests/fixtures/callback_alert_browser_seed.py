"""Move only explicitly supplied callbacks in an isolated browser-test database."""

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.db import SessionLocal, engine, now  # noqa: E402
from app.models import Lead, User  # noqa: E402

if os.environ.get("ENVIRONMENT") != "test" or not engine.url.database.endswith("_test"):
    raise RuntimeError("Callback fixtures require a disposable test database")
data = json.load(sys.stdin)
assert 1 <= len(data["lead_ids"]) <= 150
assert type(data["minutes"]) is int and -525600 <= data["minutes"] <= 525600
with SessionLocal.begin() as db:
    user = db.get(User, data["caller_id"])
    assert user and user.org_id == data["org_id"] and user.role == "telecaller"
    for identity in data["lead_ids"]:
        lead = db.get(Lead, identity)
        assert lead and lead.org_id == user.org_id and lead.owner_id == user.id
        lead.follow_up = now() + timedelta(minutes=data["minutes"])
print(json.dumps({"updated_callbacks": len(data["lead_ids"])}))
