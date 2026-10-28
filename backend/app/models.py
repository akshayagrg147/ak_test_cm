from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Entity, now


class Organization(Entity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(default=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    cursor: Mapped[int] = mapped_column(default=0)
    deleted: Mapped[bool] = mapped_column(default=False)


class User(Entity, Base):
    __tablename__ = "users"
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(default=True)
    totp_secret: Mapped[str | None] = mapped_column(Text)
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    totp_last_step: Mapped[int] = mapped_column(default=0)
    deleted: Mapped[bool] = mapped_column(default=False)


class AuthSession(Entity, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(default=False)
    support_org: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    support_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acting_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    acting_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_session_id: Mapped[str | None] = mapped_column(ForeignKey("auth_sessions.id"))


class LoginGuard(Base):
    __tablename__ = "login_guards"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    window: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Scoped(Entity):
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Lead(Scoped, Base):
    __tablename__ = "leads"
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    city: Mapped[str] = mapped_column(String(100), default="")
    state: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(30), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="new")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    stage: Mapped[str] = mapped_column(String(60), default="new")
    dnd: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(80), default="")
    custom: Mapped[dict] = mapped_column(JSON, default=dict)
    last_contact: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lost_reason: Mapped[str] = mapped_column(Text, default="")
    reported_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    deleted: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (Index("ix_lead_org_phone", "org_id", "phone"),)


class Assignment(Scoped, Base):
    __tablename__ = "assignments"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    previous_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(60))


class Note(Scoped, Base):
    __tablename__ = "notes"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)


class PhoneCall(Scoped, Base):
    __tablename__ = "phone_calls"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(100))
    device_call_id: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration: Mapped[int] = mapped_column(default=0)
    recording_state: Mapped[str] = mapped_column(String(30), default="unavailable")
    __table_args__ = (UniqueConstraint("org_id", "user_id", "device_id", "device_call_id"),)


class ManualCall(Scoped, Base):
    __tablename__ = "manual_calls"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    duration: Mapped[int] = mapped_column(default=0)
    outcome: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, default="")
    order_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    phone_call_id: Mapped[str | None] = mapped_column(ForeignKey("phone_calls.id"), unique=True)
    request_id: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("org_id", "user_id", "request_id"),)


class Attachment(Scoped, Base):
    __tablename__ = "attachments"
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), index=True)
    property_id: Mapped[str | None] = mapped_column(ForeignKey("properties.id"), index=True)
    note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"))
    phone_call_id: Mapped[str | None] = mapped_column(ForeignKey("phone_calls.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(240))
    mime: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)


class Task(Scoped, Base):
    __tablename__ = "tasks"
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="task")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    state: Mapped[str] = mapped_column(String(20), default="open")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Definition(Scoped, Base):
    __tablename__ = "definitions"
    kind: Mapped[str] = mapped_column(String(30))
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (UniqueConstraint("org_id", "kind", "key"),)


class SavedView(Scoped, Base):
    __tablename__ = "saved_views"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20), default="leads")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)


class Audit(Scoped, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Automation(Scoped, Base):
    __tablename__ = "automations"
    name: Mapped[str] = mapped_column(String(120))
    trigger: Mapped[str] = mapped_column(String(30))
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    action: Mapped[str] = mapped_column(String(30))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)


class Job(Scoped, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class AutomationRun(Scoped, Base):
    __tablename__ = "automation_runs"
    rule_id: Mapped[str] = mapped_column(ForeignKey("automations.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"))
    state: Mapped[str] = mapped_column(String(20))
    error: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("rule_id", "job_id"),)


class Attendance(Scoped, Base):
    __tablename__ = "attendance"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    checked_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checked_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    auto_closed: Mapped[bool] = mapped_column(default=False)
    location: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("org_id", "user_id", "day"),)


class TimeEntry(Scoped, Base):
    __tablename__ = "time_entries"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    submitter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)
    hours: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str] = mapped_column(Text, default="")


class Leave(Scoped, Base):
    __tablename__ = "leave_requests"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    submitter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str] = mapped_column(Text, default="")


class PayProfile(Scoped, Base):
    __tablename__ = "pay_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    daily_target: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=8)
    pay_basis: Mapped[str] = mapped_column(String(20), default="work")
    call_hourly_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class ScheduleException(Scoped, Base):
    __tablename__ = "schedule_exceptions"
    day: Mapped[date] = mapped_column(Date)
    working: Mapped[bool] = mapped_column(default=False)
    label: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("org_id", "day"),)


class Integration(Scoped, Base):
    __tablename__ = "integrations"
    provider: Mapped[str] = mapped_column(String(30))
    secret: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("org_id", "provider"),)


class SyncRun(Scoped, Base):
    __tablename__ = "sync_runs"
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id"))
    state: Mapped[str] = mapped_column(String(20))
    imported: Mapped[int] = mapped_column(default=0)
    duplicates: Mapped[int] = mapped_column(default=0)
    invalid: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(Text, default="")


class Provenance(Scoped, Base):
    __tablename__ = "provenance"
    provider: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(120))
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    __table_args__ = (UniqueConstraint("org_id", "provider", "external_id"),)


class ImportRun(Scoped, Base):
    __tablename__ = "import_runs"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("org_id", "user_id", "digest"),)


class Backup(Scoped, Base):
    __tablename__ = "backups"
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    size: Mapped[int] = mapped_column(Integer)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Property(Scoped, Base):
    __tablename__ = "properties"
    title: Mapped[str] = mapped_column(String(180))
    reference: Mapped[str] = mapped_column(String(60))
    project: Mapped[str] = mapped_column(String(160), default="")
    developer: Mapped[str] = mapped_column(String(160), default="")
    property_type: Mapped[str] = mapped_column(String(30))
    listing_type: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(100))
    locality: Mapped[str] = mapped_column(String(120), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    area_sqft: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    possession: Mapped[str] = mapped_column(String(80), default="")
    rera_number: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    amenities: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="available")
    archived: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint("org_id", "reference", name="uq_property_reference"),)


class BuyerRequirement(Scoped, Base):
    __tablename__ = "buyer_requirements"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), unique=True)
    purpose: Mapped[str] = mapped_column(String(20), default="buy")
    budget_min: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    city: Mapped[str] = mapped_column(String(100), default="")
    localities: Mapped[list] = mapped_column(JSON, default=list)
    property_types: Mapped[list] = mapped_column(JSON, default=list)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    timeline: Mapped[str] = mapped_column(String(100), default="")
    financing: Mapped[str] = mapped_column(String(30), default="undecided")
    notes: Mapped[str] = mapped_column(Text, default="")


class SiteVisit(Scoped, Base):
    __tablename__ = "site_visits"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(default=60)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")


class FieldHandoff(Scoped, Base):
    __tablename__ = "field_handoffs"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    executive_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    visit_id: Mapped[str] = mapped_column(ForeignKey("site_visits.id"), unique=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    current: Mapped[bool] = mapped_column(default=True)
    brief: Mapped[str] = mapped_column(Text)
    meeting_point: Mapped[str] = mapped_column(String(500))
    feedback: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(String(200), default="")
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    version: Mapped[int] = mapped_column(default=1)
    request_id: Mapped[str] = mapped_column(String(100))
    request_digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("org_id", "request_id", name="uq_field_handoff_request"),
        Index("uq_current_field_handoff", "org_id", "lead_id", unique=True, postgresql_where=current.is_(True)),
        CheckConstraint("status IN ('pending', 'accepted', 'follow_up', 'ready_for_booking', 'closed', 'cancelled')", name="ck_field_handoff_status"),
    )


class Booking(Scoped, Base):
    __tablename__ = "bookings"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reference: Mapped[str] = mapped_column(String(80))
    agreed_price: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    token_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    commission: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    booked_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("org_id", "reference", name="uq_booking_reference"),)


class SubscriptionPlan(Entity, Base):
    __tablename__ = "subscription_plans"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    yearly_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    seats: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)


class CompanySubscription(Scoped, Base):
    __tablename__ = "company_subscriptions"
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("subscription_plans.id"))
    plan_name: Mapped[str] = mapped_column(String(100), default="Trial")
    cycle: Mapped[str] = mapped_column(String(20), default="monthly")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    seats: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(20), default="trial")
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("org_id", name="uq_company_subscription"),)


class PlatformBilling(Base):
    __tablename__ = "platform_billing"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default="default")
    payee_name: Mapped[str] = mapped_column(String(160), default="")
    upi_id: Mapped[str] = mapped_column(String(160), default="")
    instructions: Mapped[str] = mapped_column(String(2000), default="")
    qr_storage_key: Mapped[str] = mapped_column(String(100), default="")
    qr_mime: Mapped[str] = mapped_column(String(60), default="")
    qr_name: Mapped[str] = mapped_column(String(200), default="")
    upi_enabled: Mapped[bool] = mapped_column(default=True)
    cod_enabled: Mapped[bool] = mapped_column(default=False)
    cod_instructions: Mapped[str] = mapped_column(String(2000), default="")


class SubscriptionPayment(Scoped, Base):
    __tablename__ = "subscription_payments"
    plan_id: Mapped[str] = mapped_column(ForeignKey("subscription_plans.id"))
    submitted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    receipt_id: Mapped[str | None] = mapped_column(ForeignKey("attachments.id"))
    plan_name: Mapped[str] = mapped_column(String(100))
    seats: Mapped[int] = mapped_column(Integer)
    cycle: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference: Mapped[str | None] = mapped_column(String(80), unique=True)
    payment_method: Mapped[str] = mapped_column(String(10), default="upi")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str] = mapped_column(String(2000), default="")
    request_id: Mapped[str] = mapped_column(String(100))
    __table_args__ = (
        UniqueConstraint("org_id", "request_id", name="uq_subscription_payment_request"),
        CheckConstraint("payment_method IN ('upi', 'cod')", name="ck_subscription_payment_method"),
        CheckConstraint(
            "(payment_method = 'upi' AND reference IS NOT NULL) OR (payment_method = 'cod' AND reference IS NULL)",
            name="ck_subscription_payment_reference",
        ),
    )
