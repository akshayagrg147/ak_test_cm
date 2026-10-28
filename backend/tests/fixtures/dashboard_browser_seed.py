"""Date only explicitly supplied browser-test clients in a disposable database."""

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.db import SessionLocal, engine, now  # noqa: E402
from app.models import Lead, User  # noqa: E402

if os.environ.get("ENVIRONMENT") != "test" or not engine.url.database.endswith("_test"):
    raise RuntimeError("Dashboard fixtures require a disposable test database")
data = json.load(sys.stdin)
with SessionLocal.begin() as db:
    member = db.get(User, data["caller_id"])
    assert member and member.org_id == data["org_id"] and member.role == "telecaller"
    for index, identity in enumerate(data["lead_ids"]):
        lead = db.get(Lead, identity)
        assert lead and lead.org_id == member.org_id and lead.owner_id == member.id
        lead.created_at = now() - timedelta(days=index, minutes=5)
        if index < 2:
            lead.status = "follow-up"
            lead.follow_up = now() - timedelta(hours=index + 1)
print(json.dumps({"dated_clients": len(data["lead_ids"])}))
