from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .common import csv_response, lead_dump, rows, visible_lead_ids
from .db import get_db, now
from .leads import lead_query
from .models import Definition, Lead, ManualCall, PhoneCall, Task, User
from .security import current, fail, workspace

router = APIRouter(prefix="/api", tags=["Reports & notifications"])


def analytics_data(db, ctx, from_date=None, to_date=None, owner_id=None, *, dashboard_days=None):
    workspace(ctx)
    end = to_date or now()
    start = from_date or end - timedelta(days=30)
    if start.tzinfo is None or end.tzinfo is None or end <= start or (end - start).days > 732:
        fail("invalid_date_range", "Use a timezone-aware date range of up to two years", 422)
    all_leads = list(db.scalars(lead_query(ctx, owner_id=owner_id)))
    lead_ids = {r.id for r in all_leads}
    leads = [r for r in all_leads if start <= r.created_at < end]
    prior = [r for r in all_leads if start - (end - start) <= r.created_at < start]
    manual_query = rows(db, ManualCall, ctx.org_id).where(
        ManualCall.created_at >= start, ManualCall.created_at < end, ManualCall.lead_id.in_(lead_ids)
    )
    phone_query = rows(db, PhoneCall, ctx.org_id).where(
        PhoneCall.started_at >= start, PhoneCall.started_at < end, PhoneCall.lead_id.in_(lead_ids)
    )
    if ctx.role in {"telecaller", "field_executive"}:
        manual_query = manual_query.where(ManualCall.user_id == ctx.id)
        phone_query = phone_query.where(PhoneCall.user_id == ctx.id)
    elif owner_id and owner_id != "unassigned":
        manual_query = manual_query.where(ManualCall.user_id == owner_id)
        phone_query = phone_query.where(PhoneCall.user_id == owner_id)
    manuals, phones = list(db.scalars(manual_query)), list(db.scalars(phone_query))
    # A linked manual outcome contributes business value, but no second call/duration.
    standalone = [r for r in manuals if not r.phone_call_id]
    total_calls = len(phones) + len(standalone)
    declared = sum(r.duration for r in standalone)
    observed = sum(r.duration for r in phones)
    total_seconds = declared + observed
    missed = sum(r.result in ["missed", "rejected"] for r in phones) + sum(
        r.outcome == "not-picked" for r in standalone
    )
    orders = [r for r in manuals if r.order_value > 0]
    revenue = sum((r.order_value for r in orders), Decimal(0))
    zone = ZoneInfo(ctx.org.settings.get("workplace", {}).get("timezone", "Asia/Kolkata"))
    hourly = Counter(
        [r.started_at.astimezone(zone).hour for r in phones] + [r.created_at.astimezone(zone).hour for r in standalone]
    )
    board = defaultdict(lambda: {"calls": 0, "seconds": 0, "order_value": Decimal(0)})
    for r in [*standalone, *phones]:
        board[r.user_id]["calls"] += 1
        board[r.user_id]["seconds"] += r.duration
    for r in manuals:
        board[r.user_id]["order_value"] += r.order_value
    members = {u.id: u for u in db.scalars(rows(db, User, ctx.org_id))}
    leaderboard = [
        {
            "user_id": key,
            "name": members[key].name,
            "calls": value["calls"],
            "minutes": round(value["seconds"] / 60, 1),
            "order_value": str(value["order_value"]),
        }
        for key, value in board.items()
        if key in members
    ]
    cities = {}
    for r in leads:
        item = cities.setdefault(
            r.city or "Unspecified", {"city": r.city or "Unspecified", "leads": 0, "converted": 0, "order_value": "0"}
        )
        item["leads"] += 1
        item["converted"] += r.status == "converted"
    by_id = {r.id: r for r in all_leads}
    for r in manuals:
        city = by_id[r.lead_id].city or "Unspecified"
        item = cities.setdefault(city, {"city": city, "leads": 0, "converted": 0, "order_value": "0"})
        item["order_value"] = str(Decimal(item["order_value"]) + r.order_value)
    result = {
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "timezone": str(zone),
        "metrics": {
            "leads": len(leads),
            "prior_leads": len(prior),
            "assigned": sum(r.owner_id is not None for r in leads),
            "unassigned": sum(r.owner_id is None for r in leads),
            "converted": sum(r.status == "converted" for r in leads),
            "conversion_rate": round(sum(r.status == "converted" for r in leads) / len(leads) * 100, 1) if leads else 0,
            "calls": total_calls,
            "observed_seconds": observed,
            "declared_seconds": declared,
            "talk_seconds": total_seconds,
            "average_call_seconds": round(total_seconds / total_calls) if total_calls else 0,
            "missed_rate": round(missed / total_calls * 100, 1) if total_calls else 0,
            "order_value": str(revenue),
            "average_order_value": str((revenue / len(orders)).quantize(Decimal(".01"))) if orders else "0.00",
            "overdue": sum(r.follow_up is not None and r.follow_up < now() for r in all_leads),
            "upcoming": sum(r.follow_up is not None and r.follow_up >= now() for r in all_leads),
            "stale": sum(r.created_at < now() - timedelta(hours=48) and r.last_contact is None for r in all_leads),
        },
        "statuses": dict(Counter(r.status for r in leads)),
        "sources": dict(Counter(r.source for r in leads)),
        "outcomes": dict(Counter(r.outcome for r in manuals)),
        "hourly": [{"hour": h, "calls": hourly[h]} for h in range(24)],
        "leaderboard": sorted(leaderboard, key=lambda r: -r["calls"]),
        "cities": list(cities.values()),
        "latest": [lead_dump(db, r) for r in sorted(leads, key=lambda r: r.created_at, reverse=True)[:6]],
        "definitions": "Lead and status/source counts use creation time in [from,to). Call metrics use call time; linked manual outcomes add no duplicate calls. Observed seconds are from devices; declared seconds are standalone manual interactions. Attention counts use all currently visible leads. Payroll uses its separate approved ledger.",
    }
    if dashboard_days:
        stamp = end
        local_now = stamp.astimezone(zone)

        def key_of(value):
            local = value.astimezone(zone)
            return local.hour if dashboard_days == 1 else local.date()

        if dashboard_days == 1:
            buckets = list(range(local_now.hour + 1))
            labels = {hour: f"{hour:02}:00" for hour in buckets}
        else:
            buckets = [start.astimezone(zone).date() + timedelta(days=i) for i in range(dashboard_days)]
            labels = {day: day.strftime("%d %b") for day in buckets}
        lead_counts = Counter(key_of(lead.created_at) for lead in leads)
        call_counts = Counter([key_of(p.started_at) for p in phones] + [key_of(m.created_at) for m in standalone])
        stages = Counter(lead.stage for lead in leads)
        stage_definitions = list(
            db.scalars(
                rows(db, Definition, ctx.org_id)
                .where(Definition.kind == "stage")
                .order_by(Definition.position, Definition.id)
            )
        )
        stage_labels = {d.key: d.label for d in stage_definitions if d.active}
        closed_stages = {"won", "lost"} | {d.key for d in stage_definitions if d.config.get("closed", False)}
        eligible = [
            lead
            for lead in all_leads
            if not lead.dnd and lead.status not in {"lost", "converted"} and lead.stage not in closed_stages
        ]
        today_end = local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        priority = []
        for lead in eligible:
            reason = (
                "overdue"
                if lead.follow_up and lead.follow_up < stamp
                else "due_today"
                if lead.follow_up and lead.follow_up < today_end
                else "first_contact"
                if not lead.last_contact
                else None
            )
            if reason:
                priority.append((lead, reason))
        priority.sort(
            key=lambda pair: (
                {"overdue": 0, "due_today": 1, "first_contact": 2}[pair[1]],
                pair[0].follow_up or pair[0].created_at,
                pair[0].id,
            )
        )
        result["metrics"].update(
            visible_leads=len(all_leads),
            active_leads=len(eligible),
            actionable_overdue=sum(lead.follow_up is not None and lead.follow_up < stamp for lead in eligible),
            needs_first_contact=sum(lead.last_contact is None for lead in eligible),
        )
        result.update(
            trend=[
                {"key": str(key), "label": labels[key], "leads": lead_counts[key], "calls": call_counts[key]}
                for key in buckets
            ],
            pipeline=[
                {
                    "key": key,
                    "label": stage_labels.get(key, key.replace("_", " ").capitalize() or "No stage"),
                    "count": stages[key],
                }
                for key in [*stage_labels, *[s for s in stages if s not in stage_labels]]
            ],
            call_results={**dict(Counter(p.result for p in phones)), "manual": len(standalone)},
            priority=[{"lead": lead_dump(db, lead), "reason": reason} for lead, reason in priority[:6]],
            priority_total=len(priority),
            period_days=dashboard_days,
        )
    return result


@router.get("/dashboard")
def dashboard(
    days: int = Query(7, ge=1, le=30),
    owner_id: str | None = None,
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    workspace(ctx)
    if days not in {1, 7, 30}:
        fail("invalid_dashboard_period", "Choose Today, Last 7 days or Last 30 days", 422)
    stamp = now()
    zone = ZoneInfo(ctx.org.settings.get("workplace", {}).get("timezone", "Asia/Kolkata"))
    start = stamp.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    return analytics_data(db, ctx, start, max(stamp, start + timedelta(microseconds=1)), owner_id, dashboard_days=days)


@router.get("/analytics")
def analytics(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    owner_id: str | None = None,
    export: bool = False,
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    result = analytics_data(db, ctx, from_date, to_date, owner_id)
    return (
        csv_response(
            [{"metric": k, "value": v} for k, v in result["metrics"].items()], ["metric", "value"], "analytics.csv"
        )
        if export
        else result
    )


@router.get("/notifications")
def notifications(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    leads = list(
        db.scalars(
            lead_query(ctx)
            .where(
                (
                    (Lead.follow_up < now())
                    | ((Lead.created_at < now() - timedelta(hours=48)) & Lead.last_contact.is_(None))
                )
            )
            .order_by(Lead.follow_up.asc().nulls_last())
            .limit(30)
        )
    )
    tasks_query = rows(db, Task, ctx.org_id).where(
        Task.owner_id == ctx.id, Task.state == "open", Task.due_at < now() + timedelta(days=1)
    )
    if ctx.role in {"telecaller", "field_executive"}:
        tasks_query = tasks_query.where((Task.lead_id.is_(None)) | (Task.lead_id.in_(visible_lead_ids(ctx))))
    from .field_work import handoff_query
    from .models import FieldHandoff

    field_alerts = (
        [
            {
                "id": "field-" + item.id,
                "title": "Accept client handoff" if item.status == "pending" else "Client ready for booking",
                "description": db.get(Lead, item.lead_id).name,
                "url": "/app/leads/" + item.lead_id,
            }
            for item in db.scalars(
                handoff_query(ctx)
                .where(
                    FieldHandoff.current.is_(True),
                    FieldHandoff.status == ("pending" if ctx.role == "field_executive" else "ready_for_booking"),
                )
                .limit(20)
            )
        ]
        if ctx.role in {"admin", "manager", "field_executive"}
        else []
    )
    return (
        [
            {
                "id": lead.id,
                "title": "Callback overdue" if lead.follow_up else "Lead needs first contact",
                "description": lead.name,
                "url": f"/app/leads/{lead.id}",
            }
            for lead in leads
        ]
        + [
            {"id": t.id, "title": "Task due", "description": t.title, "url": "/app/tasks"}
            for t in db.scalars(tasks_query.limit(30))
        ]
        + field_alerts
    )
