from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Role = Literal["admin", "manager", "telecaller", "field_executive"]
Status = Literal["new", "follow-up", "not-picked", "converted", "lost"]
Source = Literal["manual", "website", "referral", "indiamart", "justdial", "tradeindia", "99acres", "magicbricks", "housing", "walk-in", "property-expo", "broker"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def timezone_required(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("Include a timezone in date/time values")
        return value


class LoginIn(Payload):
    phone: str = Field(min_length=6, max_length=30)
    password: str = Field(min_length=1, max_length=200)
    challenge: str | None = None
    code: str | None = Field(default=None, pattern=r"^\d{6}$")


class PasswordIn(Payload):
    current: str
    password: str = Field(min_length=12, max_length=200)


class MemberIn(Payload):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    password: str = Field(min_length=12, max_length=200)
    role: Role


class MemberPatch(Payload):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=200)


class CompanyAdminPatch(Payload):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=200)


class CompanyProfile(Payload):
    contact_name: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=500)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=240)
    rera_number: str = Field(default="", max_length=100)
    gst_number: str = Field(default="", max_length=30)

    @field_validator("website")
    @classmethod
    def safe_website(cls, value):
        from urllib.parse import urlparse

        if value and (urlparse(value).scheme not in {"https", "http"} or not urlparse(value).netloc):
            raise ValueError("Website must start with https:// or http://")
        return value

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        import re

        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class OrganizationIn(Payload):
    name: str = Field(min_length=2, max_length=160)
    admin: MemberIn
    industry: Literal["general", "real_estate"] = "general"
    brand_name: str = Field(default="", max_length=160)
    profile: CompanyProfile = Field(default_factory=CompanyProfile)
    trial_days: int = Field(default=14, ge=1, le=90)


class OrganizationPatch(Payload):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    active: bool | None = None
    brand_name: str | None = Field(default=None, max_length=160)
    profile: CompanyProfile | None = None


def unique_interests(values):
    seen, result = set(), []
    for value in values:
        if value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result


Interest = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=r"^[^\x00-\x1f\x7f|]+$")
]
Interests = Annotated[list[Interest], Field(max_length=30), AfterValidator(unique_interests)]


class LeadIn(Payload):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=6, max_length=30)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    source: Source = "manual"
    status: Status = "new"
    stage: str = "new"
    dnd: bool = False
    notes: str = Field(default="", max_length=10000)
    category: str = Field(default="", max_length=80)
    interests: Interests = Field(default_factory=list)
    custom: dict = Field(default_factory=dict)
    details: dict = Field(default_factory=dict)
    follow_up: datetime | None = None
    allow_duplicate: bool = False

    @model_validator(mode="after")
    def followup(self):
        if self.status == "follow-up" and not self.follow_up:
            raise ValueError("A follow-up date and time is required")
        if self.status == "lost":
            raise ValueError("Use the outcome action with a lost reason and manager")
        return self


class LeadPatch(Payload):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    source: Source | None = None
    stage: str | None = None
    dnd: bool | None = None
    notes: str | None = Field(default=None, max_length=10000)
    category: str | None = Field(default=None, max_length=80)
    interests: Interests | None = None
    custom: dict | None = None
    details: dict | None = None


class AssignIn(Payload):
    lead_ids: list[str] = Field(min_length=1, max_length=500)
    owner_id: str


class NoteIn(Payload):
    text: str = Field(min_length=1, max_length=10000)


class OutcomeIn(Payload):
    outcome: Status
    notes: str = Field(default="", max_length=10000)
    duration: int = Field(default=0, ge=0, le=86400)
    order_value: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("9999999999.99"), decimal_places=2)
    follow_up: datetime | None = None
    manager_id: str | None = None
    request_id: str = Field(min_length=8, max_length=100)
    phone_call_id: str | None = None

    @model_validator(mode="after")
    def valid_outcome(self):
        if self.outcome == "follow-up" and not self.follow_up:
            raise ValueError("Follow-up requires a date and time")
        if self.outcome == "lost" and (not self.notes or not self.manager_id):
            raise ValueError("Lost deals require a reason and an active manager")
        return self


class TaskIn(Payload):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10000)
    lead_id: str | None = None
    owner_id: str | None = None
    kind: Literal["callback", "task", "meeting", "reminder"] = "task"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: datetime
    state: Literal["open", "completed", "cancelled"] = "open"


class GeoIn(Payload):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy: float = Field(ge=0, le=10000, allow_inf_nan=False)


class Workplace(GeoIn):
    name: str = Field(min_length=2, max_length=120)
    radius: int = Field(default=200, ge=25, le=5000)
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        from zoneinfo import ZoneInfo

        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("Use a valid IANA timezone") from exc
        return value


class SettingsIn(Payload):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    workplace: Workplace | None = None
    weekdays: list[int] = Field(default=[0, 1, 2, 3, 4], max_length=7)
    daily_hours: Decimal = Field(default=8, gt=0, le=24)
    pharma_enabled: bool = False
    brand_name: str = Field(default="", max_length=160)

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value):
        if len(set(value)) != len(value) or any(d < 0 or d > 6 for d in value):
            raise ValueError("Working days must be unique values from 0 (Monday) to 6")
        return value


class TimeIn(Payload):
    user_id: str | None = None
    day: date
    hours: Decimal = Field(gt=0, le=24, decimal_places=4)
    category: Literal["calling", "event", "training", "admin", "other"] = "calling"
    description: str = Field(min_length=3, max_length=2000)


class LeaveIn(Payload):
    user_id: str | None = None
    starts_on: date
    ends_on: date
    kind: Literal["casual", "sick", "planned", "personal", "other"] = "casual"
    reason: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def range_check(self):
        if self.ends_on < self.starts_on or (self.ends_on - self.starts_on).days > 366:
            raise ValueError("Leave must be an ordered range of at most 367 days")
        return self


class ReviewIn(Payload):
    state: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)


class PayIn(Payload):
    hourly_rate: Decimal = Field(ge=0, le=1000000, decimal_places=2)
    daily_target: Decimal = Field(gt=0, le=24, decimal_places=2)
    pay_basis: Literal["work", "office_calls"] = "work"
    call_hourly_rate: Decimal = Field(default=0, ge=0, le=1000000, decimal_places=2)


class ExceptionIn(Payload):
    day: date
    working: bool
    label: str = Field(min_length=2, max_length=120)


class DefinitionIn(Payload):
    kind: Literal["category", "field", "stage"]
    key: str = Field(pattern=r"^[a-z][a-z0-9_\-]{0,59}$")
    label: str = Field(min_length=1, max_length=100)
    config: dict = Field(default_factory=dict)
    position: int = Field(default=0, ge=0, le=999)
    active: bool = True


class AutomationIn(Payload):
    name: str = Field(min_length=2, max_length=120)
    trigger: Literal["lead_created", "lead_assigned", "status_changed", "callback_due", "task_completed"]
    conditions: dict = Field(default_factory=dict)
    action: Literal["create_task", "add_note", "assign_manager"]
    config: dict = Field(default_factory=dict)
    enabled: bool = True


class ViewIn(Payload):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["leads", "analytics"] = "leads"
    filters: dict = Field(default_factory=dict)


class IntegrationIn(Payload):
    credential: str | None = Field(default=None, min_length=16, max_length=500)
    enabled: bool = True


class PhoneIn(Payload):
    device_call_id: str = Field(min_length=1, max_length=100)
    phone: str = Field(max_length=30)
    direction: Literal["incoming", "outgoing"]
    result: Literal["answered", "missed", "rejected", "unknown"]
    started_at: datetime
    duration: int = Field(ge=0, le=86400)


class PhoneSyncIn(Payload):
    device_id: str = Field(min_length=8, max_length=100)
    calls: list[PhoneIn] = Field(max_length=500)

    @model_validator(mode="after")
    def unique_call_ids(self):
        identities = [call.device_call_id for call in self.calls]
        if len(identities) != len(set(identities)):
            raise ValueError("Each device_call_id must be unique within a batch")
        return self
