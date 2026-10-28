import calendar
import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .common import audit, csv_response, dump, get_scoped, member, mutate, rows
from .db import get_db, now
from .models import Attendance, Leave, PayProfile, ScheduleException, TimeEntry, User
from .pay_activity import activity_for_month
from .schemas import ExceptionIn, GeoIn, LeaveIn, PayIn, ReviewIn, TimeIn
from .security import current, fail, roles, workspace

router = APIRouter(prefix="/api", tags=["Attendance, time, leave & payroll"])


def org_zone(ctx):
    return ZoneInfo(ctx.org.settings.get("workplace", {}).get("timezone", "Asia/Kolkata"))


def distance(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b - a, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def month_range(month):
    try:
        year, number = map(int, month.split("-"))
        start = date(year, number, 1)
        return start, date(year, number, calendar.monthrange(year, number)[1])
    except Exception:
        fail("invalid_month", "Use a valid month in YYYY-MM format", 422)


def close_attendance(db, record, at=None):
    if record.checked_out:
        return
    cutoff = min(at or now(), record.cutoff)
    record.checked_out = cutoff
    record.auto_closed = cutoff == record.cutoff
    seconds = max(0, int((cutoff - record.checked_in).total_seconds()))
    if seconds >= 60:
        hours = (Decimal(seconds) / Decimal(3600)).quantize(Decimal(".0001"))
        db.add(
            TimeEntry(
                org_id=record.org_id,
                user_id=record.user_id,
                submitter_id=record.user_id,
                day=record.day,
                hours=hours,
                category="other",
                description="Automatically closed at workplace midnight"
                if record.auto_closed
                else "Geofenced attendance session",
                source="attendance",
                source_id=record.id,
            )
        )


@router.post("/attendance/check-in", status_code=201)
def check_in(data: GeoIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    if ctx.user.org_id != ctx.org_id:
        fail("support_personal_action", "Support access does not create an employee attendance identity", 403)
    config = ctx.org.settings.get("workplace")
    if not config:
        fail("workplace_required", "An administrator must configure the workplace location first", 409)
    if data.accuracy > min(config["radius"], 100):
        fail("location_inaccurate", "Location accuracy is too low. Move outdoors and try again", 422)
    meters = distance(data.latitude, data.longitude, config["latitude"], config["longitude"])
    if meters > config["radius"] + 0.01:
        fail(
            "outside_workplace",
            f"You are {meters:.0f} m from the workplace; allowed radius is {config['radius']} m",
            422,
        )
    zone = org_zone(ctx)
    day = now().astimezone(zone).date()
    existing = db.scalar(rows(db, Attendance, ctx.org_id).where(Attendance.user_id == ctx.id, Attendance.day == day))
    if existing:
        fail("already_checked_in", "Attendance already exists for this workplace day", 409)
    # Catch up this user's previous open sessions before admitting a new day.
    for old in db.scalars(
        rows(db, Attendance, ctx.org_id)
        .where(Attendance.user_id == ctx.id, Attendance.checked_out.is_(None), Attendance.cutoff <= now())
        .with_for_update()
    ):
        close_attendance(db, old)
    cutoff = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    record = Attendance(
        org_id=ctx.org_id,
        user_id=ctx.id,
        day=day,
        checked_in=now(),
        cutoff=cutoff,
        location={**data.model_dump(), "distance_m": round(meters, 2), "timezone": str(zone)},
    )
    db.add(record)
    db.flush()
    audit(db, ctx, "attendance", record.id, "checked_in", "Geofenced check-in accepted")
    return dump(record)


@router.post("/attendance/check-out")
def check_out(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    record = db.scalar(
        rows(db, Attendance, ctx.org_id)
        .where(Attendance.user_id == ctx.id, Attendance.checked_out.is_(None))
        .order_by(Attendance.checked_in.desc())
        .with_for_update()
    )
    if not record:
        fail("no_open_attendance", "There is no open check-in to check out", 409)
    close_attendance(db, record)
    audit(db, ctx, "attendance", record.id, "checked_out", "Attendance closed; eligible time awaits review")
    return dump(record)


@router.get("/attendance")
def attendance(
    month: str | None = None,
    team: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    workspace(ctx)
    start, end = month_range(month or now().astimezone(org_zone(ctx)).strftime("%Y-%m"))
    query = rows(db, Attendance, ctx.org_id).where(Attendance.day >= start, Attendance.day <= end)
    if not team or ctx.role in {"telecaller", "field_executive"}:
        query = query.where(Attendance.user_id == ctx.id)
    return [
        dump(r)
        for r in db.scalars(
            query.order_by(Attendance.day.desc(), Attendance.checked_in, Attendance.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ]


def submissions_query(ctx, cls):
    workspace(ctx)
    query = rows(None, cls, ctx.org_id)
    if ctx.role in {"telecaller", "field_executive"}:
        query = query.where(cls.user_id == ctx.id)
    elif ctx.role == "manager":
        query = query.where(
            (cls.user_id == ctx.id)
            | cls.user_id.in_(select(User.id).where(User.org_id == ctx.org_id, User.role.in_(["telecaller", "field_executive"])))
        )
    return query


def submission_owner(db, ctx, user_id):
    target = user_id or ctx.id
    if ctx.role == "admin" and target == ctx.id:
        fail(
            "admin_review_only",
            "Administrators can review time and leave; personal geofenced attendance is available separately",
            403,
        )
    if ctx.role != "admin" and target != ctx.id:
        fail("permission_denied", "Submit only your own time and leave", 403)
    user = member(db, ctx, target)
    if user.role == "admin":
        fail("admin_review_only", "Manual submissions are for managers and telecallers", 422)
    return user


@router.get("/time-entries")
def time_entries(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    return [
        dump(r)
        for r in db.scalars(
            submissions_query(ctx, TimeEntry)
            .order_by(TimeEntry.day.desc(), TimeEntry.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ]


@router.post("/time-entries", status_code=201)
def submit_time(data: TimeIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    user = submission_owner(db, ctx, data.user_id)
    if data.day > now().astimezone(org_zone(ctx)).date():
        fail("future_time", "Work time cannot be submitted for a future day", 422)
    existing = list(
        db.scalars(
            rows(db, TimeEntry, ctx.org_id).where(
                TimeEntry.user_id == user.id,
                TimeEntry.day == data.day,
                TimeEntry.source == "manual",
                TimeEntry.state != "rejected",
            )
        )
    )
    if sum((r.hours for r in existing), Decimal(0)) + data.hours > 24:
        fail("daily_time_limit", "Manual time cannot exceed 24 hours per day", 422)
    record = TimeEntry(
        org_id=ctx.org_id,
        user_id=user.id,
        submitter_id=ctx.id,
        day=data.day,
        hours=data.hours,
        category=data.category,
        description=data.description,
        source="manual",
    )
    db.add(record)
    db.flush()
    audit(db, ctx, "time_entry", record.id, "submitted", "Submitted work time", {"user_id": user.id})
    return dump(record)


@router.get("/leave")
def leave_list(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    return [
        dump(r)
        for r in db.scalars(
            submissions_query(ctx, Leave)
            .order_by(Leave.starts_on.desc(), Leave.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ]


@router.post("/leave", status_code=201)
def submit_leave(data: LeaveIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    user = submission_owner(db, ctx, data.user_id)
    overlap = db.scalar(
        rows(db, Leave, ctx.org_id).where(
            Leave.user_id == user.id,
            Leave.state != "rejected",
            Leave.starts_on <= data.ends_on,
            Leave.ends_on >= data.starts_on,
        )
    )
    if overlap:
        fail("leave_overlap", "This range overlaps an approved or pending leave request", 409)
    record = Leave(org_id=ctx.org_id, user_id=user.id, submitter_id=ctx.id, **data.model_dump(exclude={"user_id"}))
    db.add(record)
    db.flush()
    audit(db, ctx, "leave", record.id, "submitted", "Submitted leave request", {"user_id": user.id})
    return dump(record)


@router.post("/{kind}/{record_id}/review")
def review(
    kind: str, record_id: str, data: ReviewIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    cls = {"time-entries": TimeEntry, "leave": Leave}.get(kind)
    if not cls:
        fail("not_found", "Review type not found", 404)
    record = get_scoped(db, cls, record_id, ctx)
    user = get_scoped(db, User, record.user_id, ctx)
    if record.user_id == ctx.id or (ctx.role == "manager" and user.role not in {"telecaller", "field_executive"}):
        fail("review_forbidden", "You cannot review yourself or another manager", 403)
    if record.state != "pending":
        fail("already_reviewed", "This request has already been reviewed", 409)
    if data.state == "approved" and not user.active:
        fail("inactive_employee", "Reactivate the employee before approving their request", 409)
    record.state, record.reviewer_id, record.reviewed_at, record.review_note = data.state, ctx.id, now(), data.note
    audit(db, ctx, kind, record.id, data.state, f"{data.state.title()} employee submission", {"user_id": user.id})
    return dump(record)


@router.put("/payroll/profiles/{user_id}")
def pay_profile(user_id: str, data: PayIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    member(db, ctx, user_id)
    record = db.scalar(rows(db, PayProfile, ctx.org_id).where(PayProfile.user_id == user_id))
    if not record:
        record = PayProfile(org_id=ctx.org_id, user_id=user_id)
        db.add(record)
    basis = data.pay_basis if "pay_basis" in data.model_fields_set else (record.pay_basis or "work")
    call_rate = data.call_hourly_rate if "call_hourly_rate" in data.model_fields_set else (record.call_hourly_rate or Decimal(0))
    if basis == "office_calls" and call_rate <= 0:
        fail("calling_rate_required", "Set a calling hourly rate greater than zero for office + calling pay", 422)
    record.pay_basis, record.call_hourly_rate = basis, call_rate
    record.hourly_rate, record.daily_target = data.hourly_rate, data.daily_target
    db.flush()
    audit(db, ctx, "pay_profile", record.id, "updated", "Employee pay configuration updated")
    return dump(record)


@router.get("/schedule-exceptions")
def schedule_exceptions(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    return [dump(r) for r in db.scalars(rows(db, ScheduleException, ctx.org_id).order_by(ScheduleException.day))]


@router.post("/schedule-exceptions")
def add_exception(data: ExceptionIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    record = db.scalar(rows(db, ScheduleException, ctx.org_id).where(ScheduleException.day == data.day))
    if not record:
        record = ScheduleException(org_id=ctx.org_id, **data.model_dump())
        db.add(record)
    else:
        record.working, record.label = data.working, data.label
    db.flush()
    return dump(record)


@router.delete("/schedule-exceptions/{record_id}")
def delete_exception(record_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    db.delete(get_scoped(db, ScheduleException, record_id, ctx))
    return {"ok": True}


def payroll_data(db, ctx, month):
    start, end = month_range(month)
    exceptions = {
        r.day: r.working
        for r in db.scalars(
            rows(db, ScheduleException, ctx.org_id).where(ScheduleException.day >= start, ScheduleException.day <= end)
        )
    }
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    working = {d for d in days if exceptions.get(d, d.weekday() in ctx.org.settings.get("weekdays", [0, 1, 2, 3, 4]))}
    users = list(db.scalars(rows(db, User, ctx.org_id).where(User.deleted.is_(False)).order_by(User.name)))
    as_of = now()
    zone = org_zone(ctx)
    activities = activity_for_month(db, ctx.org_id, [user.id for user in users], days, zone, as_of)
    def hours(value):
        return str((value / Decimal(3600)).quantize(Decimal(".0001"), rounding=ROUND_HALF_UP))
    result = []
    for user in users:
        profile = db.scalar(rows(db, PayProfile, ctx.org_id).where(PayProfile.user_id == user.id))
        rate = profile.hourly_rate if profile else Decimal(0)
        basis = profile.pay_basis if profile else "work"
        call_rate = profile.call_hourly_rate if profile else Decimal(0)
        target = profile.daily_target if profile else Decimal(str(ctx.org.settings.get("daily_hours", 8)))
        entries = list(
            db.scalars(
                rows(db, TimeEntry, ctx.org_id).where(
                    TimeEntry.user_id == user.id, TimeEntry.day >= start, TimeEntry.day <= end
                )
            )
        )
        approved, pending = Decimal(0), Decimal(0)
        work_days = {}
        for day in days:
            # No interval claims for manual time: conservatively use the greater source total.
            for state in ["approved", "pending"]:
                manual = sum(
                    (r.hours for r in entries if r.day == day and r.state == state and r.source == "manual"), Decimal(0)
                )
                attendance = sum(
                    (r.hours for r in entries if r.day == day and r.state == state and r.source == "attendance"),
                    Decimal(0),
                )
                value = min(Decimal(24), max(manual, attendance))
                work_days.setdefault(day.isoformat(), {})[state] = value
                if state == "approved":
                    approved += value
                else:
                    pending += value
        leaves = list(
            db.scalars(
                rows(db, Leave, ctx.org_id).where(
                    Leave.user_id == user.id, Leave.state == "approved", Leave.starts_on <= end, Leave.ends_on >= start
                )
            )
        )
        leave_days = {d for d in working if any(r.starts_on <= d <= r.ends_on for r in leaves)}
        activity = activities[user.id]
        base_hours = approved if basis == "work" else activity["non_call_office_seconds"] / Decimal(3600)
        call_hours = Decimal(0) if basis == "work" else activity["call_seconds"] / Decimal(3600)
        base_pay = (base_hours * rate).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        call_pay = (call_hours * call_rate).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        daily = []
        for day in activity["daily"]:
            work = work_days[day["day"]]
            if any(value for key, value in day.items() if key != "day") or any(work.values()):
                daily.append({**{key: str(value) for key, value in day.items()},
                              "approved_work_hours": str(work["approved"]), "pending_work_hours": str(work["pending"])})
        result.append(
            {
                "user_id": user.id,
                "name": user.name,
                "active": user.active,
                "hourly_rate": str(rate),
                "pay_basis": basis,
                "call_hourly_rate": str(call_rate),
                "daily_target": str(target),
                "approved_hours": str(approved.quantize(Decimal(".01"))),
                "pending_hours": str(pending.quantize(Decimal(".01"))),
                "approved_leave_days": len(leave_days),
                "working_days": len(working),
                "target_hours": str((Decimal(len(working - leave_days)) * target).quantize(Decimal(".01"))),
                "office_hours": hours(activity["office_seconds"]),
                "approved_office_hours": hours(activity["approved_office_seconds"]),
                "pending_office_hours": hours(activity["pending_office_seconds"]),
                "call_hours": hours(activity["call_seconds"]),
                "non_call_office_hours": hours(activity["non_call_office_seconds"]),
                "base_paid_hours": str(base_hours.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)),
                "call_paid_hours": str(call_hours.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)),
                "base_pay": str(base_pay),
                "call_pay": str(call_pay),
                **{key: str(value) for key, value in activity.items() if key.endswith("_seconds")},
                "answered_call_records": activity["answered_call_records"],
                "open_attendance": activity["open_attendance"],
                "daily": daily,
                "estimated_pay": str(base_pay + call_pay),
            }
        )
    return {
        "month": month,
        "timezone": str(zone),
        "as_of": as_of.isoformat(),
        "items": result,
        "totals": {
            "estimated_pay": str(sum((Decimal(row["estimated_pay"]) for row in result), Decimal(0))),
            "office_seconds": str(sum((Decimal(row["office_seconds"]) for row in result), Decimal(0))),
            "call_seconds": str(sum((Decimal(row["call_seconds"]) for row in result), Decimal(0))),
            "pending_hours": str(sum((Decimal(row["pending_hours"]) for row in result), Decimal(0))),
        },
        "policy": "Approved work method: hourly rate × approved eligible work hours, using the larger manual/attendance total per day, capped at 24h. Office + calling method: approved office attendance excluding call overlap × office rate, plus synced answered-call time × calling rate. Overlapping/duplicate call intervals count once. Call placement uses phone-reported start + duration; office-boundary placement is approximate. Manual call durations and manual time submissions do not create office attendance or paid call time. Pending/rejected office time is unpaid. Leave reduces targets, not pay hours. Each pay component is rounded once to the nearest paisa, then added. Rates apply to all months; late syncing and approvals update estimates.",
    }


@router.get("/payroll")
def payroll(month: str = Query(), ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin")
    return payroll_data(db, ctx, month)


@router.get("/payroll/export")
def payroll_export(month: str = Query(), ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    roles(ctx, "admin")
    return csv_response(
        payroll_data(db, ctx, month)["items"],
        [
            "name",
            "approved_hours",
            "pending_hours",
            "approved_leave_days",
            "target_hours",
            "hourly_rate",
            "pay_basis",
            "office_hours",
            "approved_office_hours",
            "pending_office_hours",
            "call_hours",
            "calls_during_office_seconds",
            "calls_outside_office_seconds",
            "base_paid_hours",
            "call_paid_hours",
            "call_hourly_rate",
            "base_pay",
            "call_pay",
            "estimated_pay",
        ],
        "payroll-estimate.csv",
    )
