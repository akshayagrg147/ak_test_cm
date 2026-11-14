"""Fictional "Demo Realty" workspace for showing ViaCRM to prospects.

    python -m app.demo_realty create   # once; refuses if the demo or its login phones exist
    python -m app.demo_realty reset    # weekly; replaces demo records, keeps the logins

Every person, phone number, project and amount here is invented. The logins get an
unusable random password: the owner sets real passwords in Super admin (admin) and in the
company's Team page (caller). The script never touches any other organization.
"""

import secrets
import sys
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from .common import init_org
from .db import Base, SessionLocal, now
from .models import (
    Assignment,
    Audit,
    Booking,
    BuyerRequirement,
    CompanySubscription,
    Lead,
    ManualCall,
    Note,
    Organization,
    Property,
    SiteVisit,
    Task,
    User,
)
from .security import passwords

DEMO_ID = "4dd1208e-e761-40a9-866d-ae39c4bdd50a"
DEMO_NAME = "Demo Realty"
FICTIONAL = "Fictional demo record. Not a real person, property or transaction."
# Login phones for the demo team. Invented numbers in one block; change them here if needed.
TEAM = [
    ("Demo Admin", "admin", "+919000000901"),
    ("Priya (Demo Caller)", "telecaller", "+919000000902"),
    ("Karan (Demo Caller)", "telecaller", "+919000000903"),
    ("Vikram (Demo Field)", "field_executive", "+919000000904"),
]
# Records kept by "reset": the workspace itself, its logins, pipeline/category settings and plan.
KEEP = {"organizations", "users", "definitions", "company_subscriptions", "pay_profiles"}

FIRST = ["Rahul", "Sneha", "Amit", "Pooja", "Vikas", "Neha", "Rohit", "Anjali", "Sandeep", "Kavita",
         "Manish", "Ritu", "Deepak", "Swati", "Arjun", "Meera", "Nitin", "Shalini", "Gaurav", "Divya",
         "Harsh", "Komal", "Tarun", "Payal", "Varun", "Nidhi", "Ajay", "Simran", "Mohit", "Isha"]
LAST = ["Sharma", "Verma", "Gupta", "Malhotra", "Arora", "Kapoor", "Singh", "Bansal", "Chawla", "Mehta"]
LOCALITIES = [("Gurugram", "Sector 65"), ("Gurugram", "Golf Course Extension"), ("Gurugram", "Sohna Road"),
              ("Noida", "Sector 150"), ("Noida", "Sector 75"), ("Gurugram", "Dwarka Expressway")]
SOURCES = ["website", "google-ads", "99acres", "magicbricks", "housing", "referral", "walk-in", "indiamart"]
PROPERTIES = [
    ("3 BHK in Aravali Heights (demo)", "apartment", "sale", 0, Decimal("18500000"), 1850, 3),
    ("2 BHK in Aravali Heights (demo)", "apartment", "sale", 0, Decimal("12500000"), 1290, 2),
    ("4 BHK penthouse, Skyline Residency (demo)", "apartment", "sale", 1, Decimal("42000000"), 3400, 4),
    ("3 BHK in Greenfield Towers (demo)", "apartment", "sale", 2, Decimal("15800000"), 1720, 3),
    ("Independent villa, Palm Grove (demo)", "villa", "sale", 2, Decimal("36000000"), 3000, 4),
    ("2 BHK in Riverstone Homes (demo)", "apartment", "sale", 3, Decimal("9800000"), 1150, 2),
    ("3 BHK in Riverstone Homes (demo)", "apartment", "sale", 4, Decimal("13900000"), 1600, 3),
    ("200 sq yd plot, Sunrise Enclave (demo)", "plot", "sale", 5, Decimal("21000000"), 1800, None),
    ("Office space, Metro Business Park (demo)", "office", "rent", 0, Decimal("140000"), 1400, None),
    ("2 BHK for rent, Lakeview Apartments (demo)", "apartment", "rent", 3, Decimal("38000"), 1100, 2),
]


def _org(db):
    org = db.get(Organization, DEMO_ID)
    if org and org.name != DEMO_NAME:
        raise SystemExit(f"Organization {DEMO_ID} is not {DEMO_NAME!r}; nothing changed")
    return org


def create():
    with SessionLocal.begin() as db:
        if _org(db):
            raise SystemExit("Demo Realty already exists; use 'reset' to refresh its records")
        used = db.scalars(select(User.phone).where(User.phone.in_([p for _, _, p in TEAM]))).all()
        if used:
            raise SystemExit(f"Demo login phones already in use: {', '.join(used)}; nothing changed")
        today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
        org = Organization(
            id=DEMO_ID,
            name=DEMO_NAME,
            settings={
                "industry": "real_estate",
                "brand_name": DEMO_NAME,
                "company_profile": {
                    "contact_name": "Demo Admin", "email": "demo@example.com", "phone": "+919000000901",
                    "address": "Demo office (fictional)", "city": "Gurugram", "state": "Haryana",
                    "website": "https://viacrm.in", "rera_number": "", "gst_number": "",
                },
            },
        )
        db.add(org)
        db.flush()
        init_org(db, org)
        for name, role, phone in TEAM:
            db.add(User(org_id=org.id, name=name, role=role, phone=phone,
                        password_hash=passwords.hash(secrets.token_urlsafe(32))))
        # A non-billed demo plan so the workspace never shows trial countdowns in recordings.
        db.add(CompanySubscription(org_id=org.id, plan_name="Demo workspace (not billed)", status="active",
                                   amount=0, seats=10, starts_on=today, ends_on=today + timedelta(days=5 * 365)))
        db.flush()
        _records(db, org)
    print(f"{DEMO_NAME} created. Logins: " + ", ".join(f"{n} {p}" for n, _, p in TEAM))
    print("Set passwords in Super admin (admin) and the company's Team page (callers) before sharing.")


def reset():
    with SessionLocal.begin() as db:
        org = _org(db)
        if not org:
            raise SystemExit("Demo Realty does not exist; run 'create' first")
        for table in reversed(Base.metadata.sorted_tables):
            if "org_id" in table.c and table.name not in KEEP:
                db.execute(delete(table).where(table.c.org_id == DEMO_ID))
        db.flush()
        _records(db, org)
    print(f"{DEMO_NAME} records were reset. Logins and passwords are unchanged.")


def _records(db, org):
    team = {u.role if u.role != "telecaller" else u.phone: u for u in db.scalars(select(User).where(User.org_id == org.id))}
    admin, callers = team["admin"], [team["+919000000902"], team["+919000000903"]]
    field = team["field_executive"]
    stamp = now()
    props = []
    for i, (title, ptype, listing, loc, price, area, beds) in enumerate(PROPERTIES):
        city, locality = LOCALITIES[loc]
        item = Property(
            org_id=org.id, title=title, reference=f"DEMO-P{i + 1:02}", project=title.split(" in ")[-1].split(",")[-1].strip(),
            developer="Fictional Developers (demo)", property_type=ptype, listing_type=listing, city=city,
            locality=locality, price=price, area_sqft=Decimal(area), bedrooms=beds, bathrooms=beds,
            possession="Ready to move" if i % 3 else "Dec 2027", description=FICTIONAL,
            amenities=["Parking", "Power backup", "Club house"][: 1 + i % 3],
        )
        db.add(item)
        props.append(item)
    db.flush()
    stages = ["new", "new", "qualified", "qualified", "site_visit", "proposal", "new", "qualified", "lost", "new"]
    leads = []
    for i in range(30):
        stage = "won" if i == 4 else stages[i % len(stages)]
        source = SOURCES[i % len(SOURCES)]
        owner = callers[i % 2] if i not in (6, 16) else None
        created = stamp - timedelta(days=i // 2, hours=2 + i % 7)
        captured = source in {"website", "google-ads", "99acres", "magicbricks", "housing", "indiamart"}
        city, locality = LOCALITIES[i % len(LOCALITIES)]
        follow = None
        if stage in {"qualified", "site_visit", "proposal"}:
            follow = stamp + timedelta(hours=(i % 4) * 8 - 10)  # both callers get overdue and upcoming callbacks
        lead = Lead(
            org_id=org.id, name=f"{FIRST[i]} {LAST[i % len(LAST)]}", phone=f"+9190000{10001 + i:05}",
            city=city, source=source, stage=stage, owner_id=owner.id if owner else None,
            status="follow-up" if follow else {"won": "converted", "lost": "lost"}.get(stage, "new"),
            category=PROPERTIES[i % 10][1], created_at=created, follow_up=follow,
            last_contact=created + timedelta(minutes=20 + i) if stage != "new" else None,
            enquiry_at=created if captured else None,
            first_response_at=created + timedelta(minutes=4 + i * 3) if captured and (stage != "new" or i % 3) else None,
            lost_reason="Budget did not match (demo)" if stage == "lost" else "",
            notes=FICTIONAL, details={"locality": locality},
        )
        db.add(lead)
        leads.append(lead)
    db.flush()
    for i, lead in enumerate(leads):
        if lead.owner_id:
            db.add(Assignment(org_id=org.id, lead_id=lead.id, owner_id=lead.owner_id, actor_id=admin.id, source="demo_seed"))
        if i < 12:
            prop = props[i % 8]
            db.add(BuyerRequirement(
                org_id=org.id, lead_id=lead.id, purpose="buy", budget_min=prop.price * Decimal("0.8"),
                budget_max=prop.price * Decimal("1.1"), city=prop.city, localities=[prop.locality],
                property_types=[prop.property_type], bedrooms=prop.bedrooms, timeline="Within 3 months",
                financing=["loan-required", "self-funded", "loan-approved"][i % 3], notes=FICTIONAL,
            ))
        if lead.stage != "new":
            db.add(ManualCall(
                org_id=org.id, lead_id=lead.id, user_id=lead.owner_id or admin.id,
                outcome=lead.status,
                duration=90 + i * 11, request_id=f"demo-call-{i}", created_at=lead.last_contact or lead.created_at,
                order_value=Decimal("18200000") if lead.stage == "won" else Decimal(0), notes="Discussed budget, location and possession timeline (demo).",
            ))
        if i < 8:
            db.add(Note(org_id=org.id, lead_id=lead.id, author_id=lead.owner_id or admin.id,
                        text=["Wants 3 BHK near school, budget 1.6-1.9 Cr (demo).", "Prefers ready-to-move; loan pre-approved (demo).",
                              "Asked for brochure and floor plan (demo).", "Will visit with family on weekend (demo).",
                              "Booked after second visit (demo).", "Comparing two projects; call back after Diwali offers (demo).",
                              "Walk-in enquiry, needs rental 2 BHK (demo).", "Investor, looking for plots (demo)."][i]))
        if lead.follow_up and i % 2 == 0:
            db.add(Task(org_id=org.id, lead_id=lead.id, owner_id=lead.owner_id or admin.id, creator_id=admin.id,
                        due_at=lead.follow_up, title="Call back with price sheet (demo)", description=FICTIONAL,
                        priority="high" if i % 4 == 0 else "normal"))
        db.add(Audit(org_id=org.id, actor_id=admin.id, entity="lead", entity_id=lead.id, action="created",
                     summary=f"Added {lead.name} (fictional demo)", created_at=lead.created_at))
    visits = [(2, 0, -2, "completed", "Liked the layout; asked about parking (demo)."), (4, 0, -5, "completed", "Family visit went well (demo)."),
              (3, 3, 1, "scheduled", ""), (5, 4, 2, "scheduled", ""), (7, 6, -1, "no-show", "")]
    for lead_i, prop_i, days, status, feedback in visits:
        lead = leads[lead_i]
        when = (stamp + timedelta(days=days)).replace(hour=6, minute=0, second=0, microsecond=0)  # 11:30 IST
        db.add(SiteVisit(org_id=org.id, lead_id=lead.id, property_id=props[prop_i].id,
                         assignee_id=field.id if lead_i % 2 else lead.owner_id or admin.id, creator_id=admin.id,
                         starts_at=when, actual_started_at=when if status == "completed" else None,
                         status=status, notes="Meet at the sales office (demo).", feedback=feedback))
    booked = leads[4]
    props[0].status = "reserved"
    db.add(Booking(org_id=org.id, lead_id=booked.id, property_id=props[0].id, agent_id=booked.owner_id or admin.id,
                   reference="DEMO-B001", agreed_price=Decimal("18200000"), token_amount=Decimal("500000"),
                   commission=Decimal("182000"), status="booked",
                   booked_on=(stamp - timedelta(days=1)).astimezone(ZoneInfo("Asia/Kolkata")).date(), notes=FICTIONAL))


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "create":
        create()
    elif action == "reset":
        reset()
    else:
        raise SystemExit("Usage: python -m app.demo_realty create|reset")
