"""One buyer ↔ property match rule, used for both "properties for this buyer" and "buyers for this property".

`match_condition()` is the SQL form both endpoints query with; `requirement_matches()` is the same rule in
Python for single pairs and for tests that prove the two forms agree.
"""

from sqlalchemy import and_, case, exists, func, or_, select

from .common import lead_condition, rows
from .models import BuyerRequirement, Definition, Lead, Property


def _norm(value):
    return (value or "").strip().lower()


def _sql_norm(column):
    return func.lower(func.trim(func.coalesce(column, "")))


def _json_list_empty(column):
    return func.coalesce(func.json_array_length(column), 0) == 0


def _json_list_contains(column, value, normalize):
    element = func.json_array_elements_text(column).table_valued("value").render_derived()
    target = element.c.value
    if normalize:
        return exists(select(1).select_from(element).where(_sql_norm(target) == _sql_norm(value)))
    return exists(select(1).select_from(element).where(target == value))


def match_condition():
    """SQL condition that a BuyerRequirement row matches a Property row."""
    return and_(
        Property.org_id == BuyerRequirement.org_id,
        Property.archived.is_(False),
        Property.status == "available",
        Property.listing_type == case((BuyerRequirement.purpose == "rent", "rent"), else_="sale"),
        BuyerRequirement.budget_min <= Property.price,
        or_(BuyerRequirement.budget_max.is_(None), BuyerRequirement.budget_max >= Property.price),
        or_(_sql_norm(BuyerRequirement.city) == "", _sql_norm(BuyerRequirement.city) == _sql_norm(Property.city)),
        or_(
            _json_list_empty(BuyerRequirement.localities),
            _json_list_contains(BuyerRequirement.localities, Property.locality, normalize=True),
        ),
        or_(
            _json_list_empty(BuyerRequirement.property_types),
            _json_list_contains(BuyerRequirement.property_types, Property.property_type, normalize=False),
        ),
        or_(BuyerRequirement.bedrooms.is_(None), BuyerRequirement.bedrooms == Property.bedrooms),
    )


def requirement_matches(requirement, prop):
    """Python mirror of match_condition() for one requirement and one property."""
    return (
        prop.org_id == requirement.org_id
        and not prop.archived
        and prop.status == "available"
        and prop.listing_type == ("rent" if requirement.purpose == "rent" else "sale")
        and requirement.budget_min <= prop.price
        and (requirement.budget_max is None or requirement.budget_max >= prop.price)
        and (not _norm(requirement.city) or _norm(requirement.city) == _norm(prop.city))
        and (not requirement.localities or _norm(prop.locality) in {_norm(v) for v in requirement.localities})
        and (not requirement.property_types or prop.property_type in requirement.property_types)
        and (requirement.bedrooms is None or requirement.bedrooms == prop.bedrooms)
    )


def closed_stage_keys(db, org_id):
    return {"won", "lost"} | {
        stage.key
        for stage in db.scalars(rows(db, Definition, org_id).where(Definition.kind == "stage"))
        if stage.config.get("closed", False)
    }


def open_buyer_condition(db, ctx):
    """Leads the user may see that are still open buyers: not deleted, closed, won or lost (DND decided separately)."""
    return and_(
        Lead.org_id == ctx.org_id,
        Lead.deleted.is_(False),
        lead_condition(ctx),
        Lead.stage.notin_(closed_stage_keys(db, ctx.org_id)),
        Lead.status.notin_(["lost", "converted"]),
    )


def buyer_match_counts(db, ctx, property_ids):
    """{property_id: contactable matching buyers} for the given properties, in one grouped query, within the user's scope."""
    if not property_ids:
        return {}
    query = (
        select(Property.id, func.count(Lead.id))
        .select_from(Property)
        .join(BuyerRequirement, match_condition())
        .join(Lead, Lead.id == BuyerRequirement.lead_id)
        .where(
            Property.org_id == ctx.org_id,
            Property.id.in_(property_ids),
            open_buyer_condition(db, ctx),
            Lead.dnd.is_(False),
        )
        .group_by(Property.id)
    )
    return {pid: count for pid, count in db.execute(query)}
