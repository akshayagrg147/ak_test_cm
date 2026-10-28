"""Database-backed durable worker. Each organization is the transaction/lock boundary."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import logging
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .common import rows
from .db import SessionLocal, now, uid
from .integrations import poll_indiamart
from .models import (
    Assignment,
    Attendance,
    Audit,
    Automation,
    AutomationRun,
    Integration,
    Job,
    Lead,
    Note,
    Organization,
    SyncRun,
    Task,
    User,
    WorkerHeartbeat,
)
from .security import lock_org
from .workforce import close_attendance

log = logging.getLogger("crm.worker")


def run_automation(db, job):
    lead = db.get(Lead, job.payload.get("lead_id"))
    if not lead or lead.org_id != job.org_id or lead.deleted:
        return
    if job.payload.get("trigger") == "callback_due" and (
        not lead.follow_up or lead.follow_up > now() or job.payload.get("follow_up") != lead.follow_up.isoformat()
    ):
        return
    rules = list(
        db.scalars(
            rows(db, Automation, job.org_id).where(
                Automation.enabled.is_(True), Automation.trigger == job.payload["trigger"]
            )
        )
    )
    errors = []
    for rule in rules:
        execution = db.scalar(
            select(AutomationRun).where(AutomationRun.rule_id == rule.id, AutomationRun.job_id == job.id)
        )
        if execution and execution.state == "success":
            continue
        if any(getattr(lead, k) != v for k, v in rule.conditions.items()):
            continue
        actor = db.get(User, job.payload.get("actor_id")) if job.payload.get("actor_id") else None
        if not actor or not actor.active or actor.org_id != job.org_id:
            actor = db.scalar(
                rows(db, User, job.org_id)
                .where(User.active.is_(True), User.role == "admin", User.deleted.is_(False))
                .order_by(User.id)
            )
        try:
            with db.begin_nested():
                if not actor:
                    raise ValueError("No active administrator can own this system action")
                if rule.action == "add_note":
                    db.add(Note(org_id=job.org_id, lead_id=lead.id, author_id=actor.id, text=rule.config["text"]))
                elif rule.action == "create_task":
                    owner = db.get(User, lead.owner_id) if lead.owner_id else actor
                    if not owner or not owner.active or owner.deleted:
                        owner = actor
                    db.add(
                        Task(
                            org_id=job.org_id,
                            lead_id=lead.id,
                            owner_id=owner.id,
                            creator_id=actor.id,
                            title=rule.config["title"],
                            due_at=now() + timedelta(minutes=rule.config.get("delay_minutes", 0)),
                        )
                    )
                elif rule.action == "assign_manager":
                    manager = db.get(User, rule.config["manager_id"])
                    if (
                        not manager
                        or manager.org_id != job.org_id
                        or not manager.active
                        or manager.deleted
                        or manager.role != "manager"
                    ):
                        raise ValueError("Selected manager is no longer active")
                    if lead.owner_id != manager.id:
                        db.add(
                            Assignment(
                                org_id=job.org_id,
                                lead_id=lead.id,
                                previous_id=lead.owner_id,
                                owner_id=manager.id,
                                actor_id=actor.id,
                                source="automation",
                            )
                        )
                        lead.owner_id = manager.id
                db.add(
                    Audit(
                        org_id=job.org_id,
                        actor_id=actor.id,
                        entity="lead",
                        entity_id=lead.id,
                        action="automation",
                        summary=f"Applied rule: {rule.name}",
                        details={"rule_id": rule.id, "job_id": job.id},
                    )
                )
                db.flush()
            if execution:
                execution.state, execution.error = "success", ""
            else:
                db.add(
                    AutomationRun(org_id=job.org_id, rule_id=rule.id, job_id=job.id, lead_id=lead.id, state="success")
                )
        except Exception as exc:
            error = str(exc)[:200] if isinstance(exc, ValueError) else "Rule execution failed; inspect server logs"
            if execution:
                execution.state, execution.error = "failed", error
            else:
                db.add(
                    AutomationRun(
                        org_id=job.org_id, rule_id=rule.id, job_id=job.id, lead_id=lead.id, state="failed", error=error
                    )
                )
            errors.append(error)
        db.flush()
    if errors:
        raise ValueError("; ".join(errors))


def process_organization(org_id):
    with SessionLocal.begin() as db:
        org = lock_org(db, org_id)
        if not org or not org.active or org.deleted:
            return
        for record in db.scalars(
            rows(db, Attendance, org_id)
            .where(Attendance.checked_out.is_(None), Attendance.cutoff <= now())
            .with_for_update()
        ):
            close_attendance(db, record)
            db.add(
                Audit(
                    org_id=org_id,
                    entity="attendance",
                    entity_id=record.id,
                    action="auto_checkout",
                    summary="Closed at workplace midnight; time awaits approval",
                )
            )
        for lead in db.scalars(rows(db, Lead, org_id).where(Lead.deleted.is_(False), Lead.follow_up <= now())):
            key = f"callback:{lead.id}:{lead.follow_up.isoformat()}"
            db.execute(
                insert(Job)
                .values(
                    id=uid(),
                    org_id=org_id,
                    kind="automation",
                    key=key,
                    payload={
                        "trigger": "callback_due",
                        "lead_id": lead.id,
                        "actor_id": None,
                        "follow_up": lead.follow_up.isoformat(),
                    },
                    state="pending",
                    attempts=0,
                    available_at=now(),
                    last_error="",
                    created_at=now(),
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
        for integration in db.scalars(
            rows(db, Integration, org_id).where(Integration.provider == "indiamart", Integration.enabled.is_(True))
        ):
            if integration.last_error.startswith("Disconnected"):
                continue
            # Safe overlapping polling: maximum one scheduled run per 15-minute bucket.
            bucket = int(now().timestamp()) // 900
            key = f"provider:{integration.id}:{bucket}"
            db.execute(
                insert(Job)
                .values(
                    id=uid(),
                    org_id=org_id,
                    kind="provider",
                    key=key,
                    payload={"integration_id": integration.id},
                    state="pending",
                    attempts=0,
                    available_at=now(),
                    last_error="",
                    created_at=now(),
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
        jobs = list(
            db.scalars(
                rows(db, Job, org_id)
                .where(Job.state == "pending", Job.available_at <= now())
                .order_by(Job.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            job.attempts += 1
            try:
                if job.kind == "automation":
                    run_automation(db, job)
                elif job.kind == "provider":
                    integration = db.get(Integration, job.payload["integration_id"])
                    if integration and integration.enabled and integration.org_id == org_id:
                        with db.begin_nested():
                            poll_indiamart(db, integration)
                job.state, job.last_error = "done", ""
            except Exception as exc:
                message = (
                    str(exc)[:300]
                    if isinstance(exc, ValueError)
                    else "Provider or worker temporarily unavailable. Verify configuration and retry."
                )
                job.last_error = message
                job.state = "failed" if job.attempts >= 5 else "pending"
                job.available_at = now() + timedelta(seconds=min(3600, 120 * 2**job.attempts))
                if job.kind == "provider":
                    integration = db.get(Integration, job.payload["integration_id"])
                    if integration:
                        integration.last_error = message
                        db.add(SyncRun(org_id=org_id, integration_id=integration.id, state="failed", error=message))
                log.warning("job failed", extra={"job_id": job.id, "attempt": job.attempts})


def tick():
    with SessionLocal.begin() as db:
        db.execute(
            insert(WorkerHeartbeat)
            .values(id="scheduler", seen_at=now())
            .on_conflict_do_update(index_elements=["id"], set_={"seen_at": now()})
        )
        orgs = list(
            db.scalars(select(Organization.id).where(Organization.active.is_(True), Organization.deleted.is_(False)))
        )
    # One slow or broken provider must not stall other organizations.
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="crm-org") as pool:
        pending = {pool.submit(process_organization, org_id): org_id for org_id in orgs}
        while pending:
            finished, _ = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
            for future in finished:
                org_id = pending.pop(future)
                try:
                    future.result()
                except Exception:
                    log.exception("organization cycle failed", extra={"org_id": org_id})
            with SessionLocal.begin() as db:
                db.execute(
                    insert(WorkerHeartbeat)
                    .values(id="scheduler", seen_at=now())
                    .on_conflict_do_update(index_elements=["id"], set_={"seen_at": now()})
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            tick()
        except Exception:
            log.exception("worker cycle failed")
        time.sleep(10)
