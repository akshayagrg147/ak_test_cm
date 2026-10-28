"""Optional fictional pitch workspace. Additive, repeatable, and development-only."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from .common import init_org
from .config import settings
from .db import SessionLocal, now
from .models import Assignment, Audit, Lead, ManualCall, Note, Organization, PayProfile, Task, User
from .security import passwords
from .seed import DEV_PASSWORD

DEMO_ID = "d2492c1e-a986-48f2-ae96-1c92a7b41e01"
DEMO_PHONE = "+919900000007"


def seed_pitch():
    if settings.environment != "development":
        raise SystemExit("Pitch fixtures require ENVIRONMENT=development")
    with SessionLocal.begin() as db:
        if db.get(Organization, DEMO_ID):
            print("Pitch workspace already exists; nothing changed")
            return
        phones = [f"+9199000000{i:02}" for i in range(7, 11)]
        if db.scalar(select(User).where(User.phone.in_(phones))):
            raise SystemExit("Pitch account phones are already in use; no records changed")
        org = Organization(
            id=DEMO_ID,
            name="Meridian Studio",
            settings={
                "brand_name": settings.brand_name,
                "weekdays": [0, 1, 2, 3, 4],
                "daily_hours": "8",
                "pharma_enabled": False,
            },
        )
        db.add(org)
        db.flush()
        init_org(db, org)
        people = []
        for name, role, number in zip(
            ["Aarav Mehta", "Nina Desai", "Rohan Shah", "Isha Rao"],
            ["admin", "manager", "telecaller", "telecaller"],
            phones,
            strict=True,
        ):
            person = User(name=name, role=role, phone=number, org_id=org.id, password_hash=passwords.hash(DEV_PASSWORD))
            db.add(person)
            people.append(person)
        db.flush()
        admin, manager, caller, caller_two = people
        for person in people:
            db.add(PayProfile(org_id=org.id, user_id=person.id, hourly_rate=Decimal("275.00"), daily_target=8))
        customers = [
            "Atlas Design House",
            "Northline Logistics",
            "Cedar & Co.",
            "Lumen Learning",
            "Harbor Technologies",
            "Willow Interiors",
            "Fieldstone Foods",
            "Nova Distribution",
            "Juniper Enterprises",
            "Maple Healthcare",
            "Pioneer Packaging",
            "Quartz Consulting",
            "Riverbend Estates",
            "Summit Equipment",
            "Terra Organics",
            "Brightside Labs",
            "Oakridge Services",
            "Alpine Supply Co.",
            "Vista Industries",
            "Indigo Wellness",
            "Elmwood Retail",
            "Greenway Traders",
            "Urban Nest",
            "Zenith Solutions",
        ]
        outcomes = ["follow-up", "new", "converted", "follow-up", "new", "not-picked", "converted", "new"]
        stamp = now()
        for i, name in enumerate(customers):
            status = outcomes[i % len(outcomes)]
            assignee = None if i in (3, 8, 15, 21) else caller if i % 2 == 0 else caller_two
            created = stamp - timedelta(days=i // 2, hours=i + 1)
            lead = Lead(
                org_id=org.id,
                name=name,
                phone=f"+91981009{i:04}",
                city=["Mumbai", "Bengaluru", "Pune", "Delhi"][i % 4],
                source=["website", "referral", "manual", "indiamart"][i % 4],
                status=status,
                stage="won" if status == "converted" else "qualified" if status == "follow-up" else "new",
                owner_id=assignee.id if assignee else None,
                created_at=created,
                last_contact=created + timedelta(hours=1) if status != "new" else None,
                follow_up=stamp + timedelta(hours=i - 5) if status == "follow-up" else None,
                notes="Fictional pitch fixture. No real customer, contact or commercial performance is represented.",
            )
            db.add(lead)
            db.flush()
            if assignee:
                db.add(
                    Assignment(
                        org_id=org.id,
                        lead_id=lead.id,
                        owner_id=assignee.id,
                        actor_id=admin.id,
                        source="development_pitch_fixture",
                    )
                )
            if status != "new":
                db.add(
                    ManualCall(
                        org_id=org.id,
                        lead_id=lead.id,
                        user_id=assignee.id if assignee else manager.id,
                        outcome=status,
                        duration=150 + i * 15,
                        request_id=f"pitch-{i}",
                        created_at=created + timedelta(hours=1),
                        order_value=Decimal(18500 + i * 1250) if status == "converted" else 0,
                        notes="Fictional discovery conversation for the development presentation.",
                    )
                )
            if i < 6:
                db.add(
                    Note(
                        org_id=org.id,
                        lead_id=lead.id,
                        author_id=admin.id,
                        text="Demo context: interested in a connected sales workspace. Confirm the team size and process at discovery.",
                    )
                )
                db.add(
                    Task(
                        org_id=org.id,
                        lead_id=lead.id,
                        owner_id=assignee.id if assignee else manager.id,
                        creator_id=admin.id,
                        due_at=stamp + timedelta(hours=i * 2 - 1),
                        title=[
                            "Share the discovery outline",
                            "Confirm the product walkthrough",
                            "Prepare onboarding plan",
                            "Review the workflow proposal",
                            "Follow up on requirements",
                            "Schedule the decision call",
                        ][i],
                        description="Fictional demonstration task.",
                        priority="high" if i in (0, 3) else "normal",
                    )
                )
            db.add(
                Audit(
                    org_id=org.id,
                    actor_id=admin.id,
                    entity="lead",
                    entity_id=lead.id,
                    action="created",
                    summary=f"Added {name} (fictional demo)",
                    created_at=created,
                )
            )
    print("Fictional Meridian Studio created. Admin phone: " + DEMO_PHONE)
    print("Uses the documented development password. Existing workspaces were preserved.")


if __name__ == "__main__":
    seed_pitch()
