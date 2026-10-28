"""Explicit development fixtures. Never runs automatically in production."""

import getpass
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from .common import init_org
from .config import settings
from .db import SessionLocal, now
from .models import Assignment, Audit, Lead, ManualCall, Organization, PayProfile, Task, User
from .security import passwords, phone

DEV_PASSWORD = "LocalCRM!2026"


def bootstrap():
    normalized = phone(input("Owner phone (include country code): "))
    password = getpass.getpass("Owner password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters")
    with SessionLocal.begin() as db:
        if db.scalar(select(User).where(User.role == "owner")):
            raise SystemExit("An owner already exists. Use the account lifecycle workflow.")
        db.add(User(name="Platform owner", phone=normalized, role="owner", password_hash=passwords.hash(password)))


def seed():
    if settings.environment != "development":
        raise SystemExit("Development seed is disabled outside ENVIRONMENT=development")
    with SessionLocal.begin() as db:
        if db.scalar(select(User)):
            print("Database already has users; seed skipped")
            return
        owner = User(
            name="Platform owner", phone="+919900000001", role="owner", password_hash=passwords.hash(DEV_PASSWORD)
        )
        org = Organization(
            name="Evergreen workspace",
            settings={"weekdays": [0, 1, 2, 3, 4], "daily_hours": "8", "pharma_enabled": False},
        )
        second = Organization(name="Northstar workspace")
        db.add_all([owner, org, second])
        db.flush()
        init_org(db, org)
        init_org(db, second)
        people = []
        for name, suffix, role, org_id in [
            ("Aarav Mehta", "002", "admin", org.id),
            ("Priya Shah", "003", "manager", org.id),
            ("Neha Kapoor", "004", "telecaller", org.id),
            ("Kabir Rao", "005", "telecaller", org.id),
            ("Northstar Admin", "006", "admin", second.id),
        ]:
            user = User(
                name=name,
                phone="+919900000" + suffix,
                role=role,
                org_id=org_id,
                password_hash=passwords.hash(DEV_PASSWORD),
            )
            people.append(user)
            db.add(user)
        db.flush()
        admin, manager, caller, caller2, _ = people
        for user in people[:4]:
            db.add(PayProfile(org_id=org.id, user_id=user.id, hourly_rate=Decimal("250"), daily_target=8))
        names = [
            "Alpine Medical Supplies",
            "Brightside Learning",
            "Cedar & Co.",
            "Dawnline Logistics",
            "Elmwood Interiors",
            "Fieldstone Foods",
            "Greenway Traders",
            "Harbor Technologies",
            "Indigo Wellness",
            "Juniper Enterprises",
            "Keystone Manufacturing",
            "Lumen Retail",
            "Maple Healthcare",
            "Nova Distribution",
            "Oakridge Services",
            "Pioneer Packaging",
            "Quartz Consulting",
            "Riverbend Estates",
            "Summit Equipments",
            "Terra Organics",
            "Urban Nest",
            "Vista Industries",
            "Willow Partners",
            "Zenith Solutions",
        ]
        statuses = ["new", "follow-up", "new", "converted", "not-picked", "new", "follow-up", "new"]
        for i, name in enumerate(names):
            status = statuses[i % len(statuses)]
            own = None if i % 4 == 0 else caller.id if i % 2 else caller2.id
            created = now() - timedelta(days=i % 20, hours=i)
            lead = Lead(
                org_id=org.id,
                name=name,
                phone=f"+91981000{i:04d}",
                city=["Mumbai", "Pune", "Bengaluru", "Delhi", "Ahmedabad"][i % 5],
                state=["Maharashtra", "Maharashtra", "Karnataka", "Delhi", "Gujarat"][i % 5],
                source=["website", "referral", "manual", "indiamart"][i % 4],
                status=status,
                stage="won" if status == "converted" else "qualified" if status == "follow-up" else "new",
                owner_id=own,
                created_at=created,
                follow_up=now() + timedelta(hours=i - 10) if status == "follow-up" else None,
                last_contact=created + timedelta(hours=1) if status != "new" else None,
                notes="Development fixture — fictional business and contact.",
            )
            db.add(lead)
            db.flush()
            if own:
                db.add(
                    Assignment(
                        org_id=org.id, lead_id=lead.id, owner_id=own, actor_id=admin.id, source="development_fixture"
                    )
                )
            if status != "new":
                db.add(
                    ManualCall(
                        org_id=org.id,
                        lead_id=lead.id,
                        user_id=own or manager.id,
                        duration=120 + 15 * i,
                        outcome=status,
                        order_value=Decimal(12000 + i * 500) if status == "converted" else 0,
                        request_id=f"fixture-{i}",
                        created_at=created + timedelta(hours=1),
                    )
                )
            if i < 6:
                db.add(
                    Task(
                        org_id=org.id,
                        lead_id=lead.id,
                        owner_id=own or manager.id,
                        creator_id=admin.id,
                        title=[
                            "Share the workflow proposal",
                            "Confirm discovery call",
                            "Review requirements",
                            "Follow up on decision",
                            "Prepare product walkthrough",
                            "Send implementation outline",
                        ][i],
                        due_at=now() + timedelta(hours=i * 3 - 4),
                        priority="high" if i == 0 else "normal",
                    )
                )
            db.add(
                Audit(
                    org_id=org.id,
                    actor_id=admin.id,
                    entity="lead",
                    entity_id=lead.id,
                    action="created",
                    summary=f"Added {lead.name}",
                    created_at=created,
                )
            )
    print("Development fixtures created. Password: " + DEV_PASSWORD)
    print(
        "Owner +919900000001 | Admin +919900000002 | Manager +919900000003 | Caller +919900000004 | Caller 2 +919900000005 | Other org +919900000006"
    )


if __name__ == "__main__":
    bootstrap() if "--bootstrap-owner" in sys.argv else seed()
