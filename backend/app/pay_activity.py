"""Employee activity used by salary estimates; independent of current lead ownership."""

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from .models import Attendance, ManualCall, PhoneCall, TimeEntry
from .security import fail


def merged(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def clipped(intervals, start, end):
    return merged((max(a, start), min(b, end)) for a, b in intervals)


def seconds(intervals):
    return sum((Decimal(str((b - a).total_seconds())) for a, b in intervals), Decimal(0))


def overlap_seconds(left, right):
    total, i, j = Decimal(0), 0, 0
    while i < len(left) and j < len(right):
        start, end = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if end > start:
            total += Decimal(str((end - start).total_seconds()))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return total


def activity_for_month(db, org_id, user_ids, days, zone, as_of):
    """Count unique elapsed intervals, clipping at local month/day edges and now.

    Call placement uses device start + connected duration. The phone does not
    provide a separate connection timestamp; placement around office boundaries
    is therefore an approximation. Manual conversation durations never affect pay.
    """
    try:
        month_start = datetime.combine(days[0], time.min, zone).astimezone(timezone.utc)
        month_end = datetime.combine(days[-1] + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    except (OverflowError, ValueError):
        fail("invalid_month", "Choose a month within the supported calendar range", 422)
    upper = min(month_end, as_of)
    buckets = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(int)
    opened = defaultdict(int)
    declared = defaultdict(lambda: Decimal(0))
    if upper > month_start:
        offices = list(
            db.scalars(
                select(Attendance).where(
                    Attendance.org_id == org_id,
                    Attendance.user_id.in_(user_ids),
                    Attendance.checked_in < upper,
                    Attendance.cutoff > month_start,
                )
            )
        )
        reviews = {
            entry.source_id: entry
            for entry in db.scalars(
                select(TimeEntry).where(
                    TimeEntry.org_id == org_id,
                    TimeEntry.source == "attendance",
                    TimeEntry.source_id.in_([office.id for office in offices]),
                )
            )
        }
        for office in offices:
            end = min(office.checked_out or as_of, office.cutoff, upper)
            start = max(office.checked_in, month_start)
            if end <= start:
                continue
            buckets[office.user_id]["recorded"].append((start, end))
            entry = reviews.get(office.id)
            state = entry.state if entry and entry.user_id == office.user_id else "pending"
            if not office.checked_out:
                opened[office.user_id] += 1
                state = "pending"
            if state in {"approved", "pending"}:
                buckets[office.user_id][state].append((start, end))
        phones = db.scalars(
            select(PhoneCall).where(
                PhoneCall.org_id == org_id,
                PhoneCall.user_id.in_(user_ids),
                PhoneCall.started_at >= month_start - timedelta(days=1),
                PhoneCall.started_at < upper,
                PhoneCall.result == "answered",
                PhoneCall.duration > 0,
            )
        )
        for call in phones:
            # The sync contract already bounds duration at 24h. Also bound legacy
            # database rows so one invalid row cannot manufacture extra pay days.
            start = max(call.started_at, month_start)
            end = min(call.started_at + timedelta(seconds=min(call.duration, 86400)), upper)
            if end > start:
                buckets[call.user_id]["calls"].append((start, end))
                counts[call.user_id] += 1
        for call in db.scalars(
            select(ManualCall).where(
                ManualCall.org_id == org_id,
                ManualCall.user_id.in_(user_ids),
                ManualCall.created_at >= month_start,
                ManualCall.created_at < upper,
                ManualCall.phone_call_id.is_(None),
                ManualCall.duration > 0,
            )
        ):
            declared[call.user_id] += Decimal(call.duration)
    output = {}
    for user_id in user_ids:
        intervals = {key: merged(value) for key, value in buckets[user_id].items()}
        daily = []
        for day in days:
            start = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
            end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
            parts = {
                key: clipped(intervals.get(key, []), start, end) for key in ["recorded", "approved", "pending", "calls"]
            }
            office, calls = seconds(parts["approved"]), seconds(parts["calls"])
            overlap = overlap_seconds(parts["approved"], parts["calls"])
            daily.append(
                {
                    "day": day.isoformat(),
                    "office_seconds": seconds(parts["recorded"]),
                    "approved_office_seconds": office,
                    "pending_office_seconds": seconds(parts["pending"]),
                    "call_seconds": calls,
                    "calls_during_office_seconds": overlap,
                    "calls_outside_office_seconds": calls - overlap,
                    "non_call_office_seconds": office - overlap,
                }
            )
        totals = {key: sum((day[key] for day in daily), Decimal(0)) for key in daily[0] if key != "day"}
        output[user_id] = {
            **totals,
            "answered_call_records": counts[user_id],
            "open_attendance": opened[user_id],
            "declared_call_seconds": declared[user_id],
            "daily": daily,
        }
    return output
