"""Backdated office fixture for the isolated browser test database only."""

import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Attendance, Lead, Organization, TimeEntry, User  # noqa: E402

if not engine.url.database.endswith("_test"):
    raise RuntimeError("Browser payroll fixtures require an isolated _test database")
payload = json.load(sys.stdin)
with SessionLocal.begin() as db:
    admin, employee = db.get(User, payload["admin_id"]), db.get(User, payload["employee_id"])
    org = db.get(Organization, admin.org_id)
    lead = db.get(Lead, payload["lead_id"])
    assert org.name.startswith("Final QA ") and employee.org_id == org.id == lead.org_id
    assert lead.owner_id == employee.id
    zone = ZoneInfo("Asia/Kolkata")
    day = datetime.now(zone).date() - timedelta(days=1)
    start = datetime.combine(day, time(9), zone).astimezone(timezone.utc)
    end = start + timedelta(hours=8)
    item = Attendance(
        org_id=org.id,
        user_id=employee.id,
        day=day,
        checked_in=start,
        checked_out=end,
        cutoff=datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc),
        location={},
    )
    db.add(item)
    db.flush()
    db.add(
        TimeEntry(
            org_id=org.id,
            user_id=employee.id,
            submitter_id=employee.id,
            day=day,
            hours=8,
            category="other",
            description="QA closed office attendance",
            source="attendance",
            source_id=item.id,
        )
    )
    print(
        json.dumps(
            {
                "day": day.isoformat(),
                "month": day.strftime("%Y-%m"),
                "call_start": (start + timedelta(hours=2)).isoformat(),
            }
        )
    )
