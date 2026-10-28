from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .business_schemas import BookingIn, BookingUpdate, PropertyIn, RequirementIn, VisitIn, VisitUpdate
from .common import REAL_ESTATE_CATEGORIES, audit, dump, get_scoped, lead_access, member, mutate, retire_healthcare_defaults, rows, lead_condition
from .db import get_db, now
from .models import Attachment, Booking, BuyerRequirement, Definition, FieldHandoff, Lead, Property, SiteVisit, User
from .security import current, fail, roles, workspace

router = APIRouter(prefix="/api", tags=["Real estate"])
LIVE_BOOKINGS = {"reserved", "booked", "closed"}


@router.post("/real-estate/setup")
def setup(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    ctx.org.settings = {**ctx.org.settings, "industry": "real_estate", "pharma_enabled": False}
    retire_healthcare_defaults(db, ctx.org_id)
    for pos, (key, label) in enumerate(
        [
            ("new", "New enquiry"),
            ("qualified", "Qualified buyer"),
            ("site_visit", "Site visit"),
            ("proposal", "Negotiation"),
            ("won", "Booked"),
            ("lost", "Lost"),
        ]
    ):
        item = db.scalar(rows(db, Definition, ctx.org_id).where(Definition.kind == "stage", Definition.key == key))
        if not item:
            db.add(
                Definition(
                    org_id=ctx.org_id,
                    kind="stage",
                    key=key,
                    label=label,
                    position=pos,
                    config={"closed": key in {"won", "lost"}, "won": key == "won", "color": "#137b65"},
                )
            )
    for pos, key in enumerate(REAL_ESTATE_CATEGORIES):
        item = db.scalar(rows(db, Definition, ctx.org_id).where(Definition.kind == "category", Definition.key == key))
        if not item:
            db.add(Definition(org_id=ctx.org_id, kind="category", key=key, label=key.title(), position=pos))
    audit(
        db,
        ctx,
        "organization",
        ctx.org_id,
        "real_estate_enabled",
        "Enabled real estate workspace defaults while preserving existing definitions and customer data",
    )
    return dump(ctx.org)


def property_record(db, ctx, property_id, available=False):
    item = get_scoped(db, Property, property_id, ctx)
    if item.archived or (available and item.status != "available"):
        fail("property_unavailable", "This property is no longer available", 409)
    return item


def property_dump(db, item):
    return {
        **dump(item),
        "files": [
            dump(f)
            for f in db.scalars(
                rows(db, Attachment, item.org_id)
                .where(Attachment.property_id == item.id)
                .order_by(Attachment.created_at)
            )
        ],
    }


@router.get("/properties")
def properties(
    q: str = "",
    status: str = "",
    property_type: str = "",
    listing_type: str = "",
    city: str = "",
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    workspace(ctx)
    if min_price is not None and max_price is not None and min_price > max_price:
        fail("invalid_price_range", "Maximum price must be at least the minimum", 422)
    query = rows(db, Property, ctx.org_id).where(Property.archived.is_(False))
    if q:
        query = query.where(
            Property.title.ilike(f"%{q[:100]}%")
            | Property.reference.ilike(f"%{q[:100]}%")
            | Property.project.ilike(f"%{q[:100]}%")
            | Property.locality.ilike(f"%{q[:100]}%")
        )
    for column, value in [
        (Property.status, status),
        (Property.property_type, property_type),
        (Property.listing_type, listing_type),
    ]:
        if value:
            query = query.where(column == value)
    if city:
        query = query.where(func.lower(Property.city) == city.strip().lower())
    if min_price is not None:
        query = query.where(Property.price >= min_price)
    if max_price is not None:
        query = query.where(Property.price <= max_price)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            property_dump(db, p)
            for p in db.scalars(
                query.order_by(Property.created_at.desc(), Property.id).offset((page - 1) * 24).limit(24)
            )
        ],
        "total": total,
        "page": page,
    }


def validate_property(db, ctx, data, existing=None):
    reference = data.reference.upper()
    duplicate = db.scalar(rows(db, Property, ctx.org_id).where(Property.reference == reference))
    if duplicate and (not existing or duplicate.id != existing.id):
        fail("duplicate_reference", "This property reference already exists, including archived inventory", 409)
    if existing and existing.status in {"reserved", "sold", "leased"}:
        fail(
            "property_locked",
            "This property has a booking. Manage its status through Bookings before editing inventory",
            409,
        )
    return {**data.model_dump(), "reference": reference}


@router.post("/properties", status_code=201)
def add_property(data: PropertyIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    item = Property(org_id=ctx.org_id, **validate_property(db, ctx, data))
    db.add(item)
    db.flush()
    audit(db, ctx, "property", item.id, "created", f"Added property {item.reference}")
    return property_dump(db, item)


@router.get("/properties/{property_id}")
def get_property(property_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    return property_dump(db, property_record(db, ctx, property_id))


@router.put("/properties/{property_id}")
def edit_property(
    property_id: str, data: PropertyIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    item = property_record(db, ctx, property_id)
    for key, value in validate_property(db, ctx, data, item).items():
        setattr(item, key, value)
    audit(db, ctx, "property", item.id, "updated", f"Updated property {item.reference}")
    return property_dump(db, item)


@router.delete("/properties/{property_id}")
def archive_property(property_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    item = property_record(db, ctx, property_id)
    if item.status in {"reserved", "sold", "leased"} or db.scalar(
        rows(db, SiteVisit, ctx.org_id).where(SiteVisit.property_id == item.id, SiteVisit.status == "scheduled")
    ):
        fail("property_in_use", "Resolve bookings and scheduled site visits before archiving this property", 409)
    item.archived = True
    audit(db, ctx, "property", item.id, "archived", f"Archived property {item.reference}")
    return {"ok": True}


@router.get("/leads/{lead_id}/requirements")
def requirements(lead_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    lead_access(db, ctx, lead_id)
    return dump(db.scalar(rows(db, BuyerRequirement, ctx.org_id).where(BuyerRequirement.lead_id == lead_id)))


@router.put("/leads/{lead_id}/requirements")
def save_requirements(
    lead_id: str, data: RequirementIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    mutate(db, ctx)
    lead_access(db, ctx, lead_id)
    item = db.scalar(rows(db, BuyerRequirement, ctx.org_id).where(BuyerRequirement.lead_id == lead_id))
    if not item:
        item = BuyerRequirement(org_id=ctx.org_id, lead_id=lead_id)
        db.add(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.flush()
    audit(db, ctx, "lead", lead_id, "requirements_updated", "Saved customer-confirmed property requirements")
    return dump(item)


@router.get("/leads/{lead_id}/property-matches")
def property_matches(lead_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    lead_access(db, ctx, lead_id)
    requirement = db.scalar(rows(db, BuyerRequirement, ctx.org_id).where(BuyerRequirement.lead_id == lead_id))
    if not requirement:
        return {"items": [], "criteria_saved": False}
    query = rows(db, Property, ctx.org_id).where(
        Property.archived.is_(False),
        Property.status == "available",
        Property.price >= requirement.budget_min,
        Property.listing_type == ("rent" if requirement.purpose == "rent" else "sale"),
    )
    if requirement.budget_max is not None:
        query = query.where(Property.price <= requirement.budget_max)
    if requirement.city:
        query = query.where(func.lower(Property.city) == requirement.city.lower())
    if requirement.localities:
        query = query.where(func.lower(Property.locality).in_([v.lower() for v in requirement.localities]))
    if requirement.property_types:
        query = query.where(Property.property_type.in_(requirement.property_types))
    if requirement.bedrooms is not None:
        query = query.where(Property.bedrooms == requirement.bedrooms)
    return {
        "items": [property_dump(db, p) for p in db.scalars(query.order_by(Property.price, Property.id).limit(100))],
        "criteria_saved": True,
    }


def visit_dump(db, item):
    lead, prop = db.get(Lead, item.lead_id), db.get(Property, item.property_id)
    return {
        **dump(item),
        "lead_name": lead.name,
        "property_title": prop.title,
        "property_reference": prop.reference,
        "assignee_name": db.get(User, item.assignee_id).name,
        "field_handoff_id": db.scalar(select(FieldHandoff.id).where(FieldHandoff.org_id == item.org_id, FieldHandoff.visit_id == item.id)),
    }


def scoped_visits(ctx):
    workspace(ctx)
    query = rows(None, SiteVisit, ctx.org_id).join(Lead, Lead.id == SiteVisit.lead_id).where(Lead.deleted.is_(False))
    if ctx.role == "telecaller":
        query = query.where(Lead.owner_id == ctx.id, (SiteVisit.assignee_id == ctx.id) | SiteVisit.id.in_(
            select(FieldHandoff.visit_id).where(FieldHandoff.org_id == ctx.org_id, FieldHandoff.current.is_(True))
        ))
    elif ctx.role == "field_executive":
        query = query.where(lead_condition(ctx), SiteVisit.assignee_id == ctx.id)
    return query


@router.get("/site-visits")
def visits(
    lead_id: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    query = scoped_visits(ctx)
    if lead_id:
        lead_access(db, ctx, lead_id)
        query = query.where(SiteVisit.lead_id == lead_id)
    if status:
        query = query.where(SiteVisit.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            visit_dump(db, v)
            for v in db.scalars(
                query.order_by(SiteVisit.starts_at.desc(), SiteVisit.id).offset((page - 1) * 50).limit(50)
            )
        ],
        "total": total,
    }


def visit_values(db, ctx, data, except_id=None, *, field_handoff=False):
    lead_access(db, ctx, data.lead_id)
    property_record(db, ctx, data.property_id, available=True)
    assignee_id = data.assignee_id or ctx.id
    if ctx.role in {"telecaller", "field_executive"} and assignee_id != ctx.id and not field_handoff:
        fail("permission_denied", "You can schedule only your own site visits", 403)
    assignee = member(db, ctx, assignee_id)
    if assignee.deleted:
        fail("invalid_member", "Select an active team member", 422)
    if data.starts_at < now() - timedelta(minutes=5) or data.starts_at > now() + timedelta(days=5 * 366):
        fail("invalid_visit_time", "Schedule the site visit in the future, within five years", 422)
    end = data.starts_at + timedelta(minutes=data.duration_minutes)
    overlapping = db.scalars(
        rows(db, SiteVisit, ctx.org_id).where(
            SiteVisit.assignee_id == assignee_id, SiteVisit.status == "scheduled", SiteVisit.starts_at < end
        )
    )
    if any(
        v.id != except_id and v.starts_at + timedelta(minutes=v.duration_minutes) > data.starts_at for v in overlapping
    ):
        fail("visit_overlap", "This team member already has a site visit at that time", 409)
    return {**data.model_dump(), "assignee_id": assignee_id}


@router.post("/site-visits", status_code=201)
def add_visit(data: VisitIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    item = SiteVisit(org_id=ctx.org_id, creator_id=ctx.id, **visit_values(db, ctx, data))
    db.add(item)
    db.flush()
    audit(
        db, ctx, "lead", item.lead_id, "site_visit_scheduled", "Scheduled a property site visit", {"visit_id": item.id}
    )
    return visit_dump(db, item)


def accessible_visit(db, ctx, visit_id):
    item = db.scalar(scoped_visits(ctx).where(SiteVisit.id == visit_id))
    if not item:
        fail("not_found", "Site visit not found", 404)
    return item


@router.put("/site-visits/{visit_id}")
def reschedule_visit(
    visit_id: str, data: VisitIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    mutate(db, ctx)
    item = accessible_visit(db, ctx, visit_id)
    from .field_work import linked_handoff
    if linked_handoff(db, ctx.org_id, visit_id=visit_id):
        fail("field_visit_managed", "Use Field work to reschedule this client's visit", 409)
    if item.status != "scheduled":
        fail("visit_closed", "Only scheduled visits can be rescheduled", 409)
    for key, value in visit_values(db, ctx, data, item.id).items():
        setattr(item, key, value)
    audit(
        db,
        ctx,
        "lead",
        item.lead_id,
        "site_visit_rescheduled",
        "Rescheduled a property site visit",
        {"visit_id": item.id},
    )
    return visit_dump(db, item)


@router.patch("/site-visits/{visit_id}")
def update_visit(
    visit_id: str, data: VisitUpdate, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    mutate(db, ctx)
    item = accessible_visit(db, ctx, visit_id)
    from .field_work import linked_handoff
    if linked_handoff(db, ctx.org_id, visit_id=visit_id):
        fail("field_visit_managed", "Use Field work to record the outcome and next step together", 409)
    if item.status != "scheduled" or data.status == "scheduled":
        fail(
            "invalid_transition", "A completed or cancelled visit cannot be changed; schedule a new visit instead", 409
        )
    if data.status in {"completed", "no-show"} and item.starts_at > now():
        fail("visit_not_started", "Record the outcome after the scheduled visit starts", 409)
    item.status, item.feedback = data.status, data.feedback
    audit(
        db, ctx, "lead", item.lead_id, "site_visit_updated", "Site visit marked " + item.status, {"visit_id": item.id}
    )
    return visit_dump(db, item)


def booking_dump(db, item):
    return {
        **dump(item),
        "lead_name": db.get(Lead, item.lead_id).name,
        "property_title": db.get(Property, item.property_id).title,
        "agent_name": db.get(User, item.agent_id).name,
    }


@router.get("/bookings")
def bookings(
    status: str = "", page: int = Query(1, ge=1), ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    workspace(ctx)
    roles(ctx, "admin", "manager")
    query = rows(db, Booking, ctx.org_id)
    if status:
        query = query.where(Booking.status == status)
    return {
        "items": [
            booking_dump(db, b)
            for b in db.scalars(query.order_by(Booking.created_at.desc(), Booking.id).offset((page - 1) * 50).limit(50))
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
    }


@router.post("/bookings", status_code=201)
def add_booking(data: BookingIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    lead_access(db, ctx, data.lead_id)
    prop = property_record(db, ctx, data.property_id, available=True)
    agent = member(db, ctx, data.agent_id)
    if agent.deleted:
        fail("invalid_member", "Select an active agent", 422)
    if data.booked_on > now().astimezone(ZoneInfo("Asia/Kolkata")).date():
        fail("future_booking", "Booking date cannot be in the future", 422)
    reference = data.reference.upper()
    if db.scalar(rows(db, Booking, ctx.org_id).where(Booking.reference == reference)):
        fail("duplicate_reference", "This booking reference already exists", 409)
    if db.scalar(
        rows(db, Booking, ctx.org_id).where(Booking.property_id == prop.id, Booking.status.in_(LIVE_BOOKINGS))
    ):
        fail("property_booked", "This property already has a live booking", 409)
    item = Booking(org_id=ctx.org_id, **{**data.model_dump(), "reference": reference})
    prop.status = "reserved"
    db.add(item)
    db.flush()
    audit(
        db,
        ctx,
        "lead",
        item.lead_id,
        "property_reserved",
        f"Reserved property {prop.reference}",
        {"booking_id": item.id},
    )
    return booking_dump(db, item)


@router.patch("/bookings/{booking_id}")
def update_booking(
    booking_id: str, data: BookingUpdate, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    item = get_scoped(db, Booking, booking_id, ctx)
    allowed = {"reserved": {"booked", "cancelled"}, "booked": {"closed", "cancelled"}}
    if data.status not in allowed.get(item.status, set()):
        fail("invalid_transition", "Choose the next booking step; closed and cancelled bookings are final", 409)
    prop = property_record(db, ctx, item.property_id)
    item.status, item.notes = data.status, data.notes
    if data.status in {"booked", "closed"}:
        from .field_work import finish_task
        handoff = db.scalar(rows(db, FieldHandoff, ctx.org_id).where(
            FieldHandoff.lead_id == item.lead_id, FieldHandoff.current.is_(True), FieldHandoff.status == "ready_for_booking"
        ))
        if handoff and db.get(SiteVisit, handoff.visit_id).property_id == item.property_id:
            finish_task(db, handoff)
            handoff.status, handoff.feedback = "closed", "Booking confirmed: " + item.reference
            handoff.updated_at, handoff.version = now(), handoff.version + 1
            audit(db, ctx, "lead", item.lead_id, "field_booking_confirmed", handoff.feedback, {"handoff_id": handoff.id, "booking_id": item.id})
    prop.status = (
        "available"
        if data.status == "cancelled"
        else ("leased" if prop.listing_type == "rent" else "sold")
        if data.status == "closed"
        else "reserved"
    )
    audit(db, ctx, "lead", item.lead_id, "booking_updated", "Booking marked " + item.status, {"booking_id": item.id})
    return booking_dump(db, item)


@router.get("/real-estate/overview")
def overview(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    prop_query = rows(db, Property, ctx.org_id).where(Property.archived.is_(False))
    inventory = list(db.scalars(prop_query))
    visits = list(
        db.scalars(
            scoped_visits(ctx)
            .where(SiteVisit.status == "scheduled", SiteVisit.starts_at >= now() - timedelta(hours=8))
            .order_by(SiteVisit.starts_at)
            .limit(6)
        )
    )
    deal_query = rows(db, Booking, ctx.org_id).where(Booking.status != "cancelled")
    if ctx.role == "telecaller":
        deal_query = deal_query.join(Lead, Lead.id == Booking.lead_id).where(
            Lead.owner_id == ctx.id, Booking.agent_id == ctx.id, Lead.deleted.is_(False)
        )
    elif ctx.role == "field_executive":
        deal_query = deal_query.join(Lead, Lead.id == Booking.lead_id).where(lead_condition(ctx), Booking.agent_id == ctx.id, Lead.deleted.is_(False))
    deals = list(db.scalars(deal_query))
    return {
        "available": sum(p.status == "available" for p in inventory),
        "inventory": len(inventory),
        "reserved": sum(p.status == "reserved" for p in inventory),
        "booked_value": str(sum((b.agreed_price for b in deals), Decimal(0))),
        "commission": str(sum((b.commission for b in deals if b.status == "closed"), Decimal(0))),
        "visits": [visit_dump(db, v) for v in visits],
        "booking_count": len(deals),
    }
