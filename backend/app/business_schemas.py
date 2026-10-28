from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .schemas import Payload

PropertyType = Literal["apartment", "villa", "plot", "office", "retail", "warehouse", "other"]
Amount = Annotated[Decimal, Field(ge=0, le=Decimal("999999999999.99"), decimal_places=2)]
ShortList = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]], Field(max_length=30)
]


class PropertyIn(Payload):
    title: str = Field(min_length=2, max_length=180)
    reference: str = Field(min_length=2, max_length=60, pattern=r"^[a-zA-Z0-9_/-]+$")
    project: str = Field(default="", max_length=160)
    developer: str = Field(default="", max_length=160)
    property_type: PropertyType = "apartment"
    listing_type: Literal["sale", "rent"] = "sale"
    city: str = Field(min_length=2, max_length=100)
    locality: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=500)
    price: Amount = Field(gt=0)
    area_sqft: Decimal = Field(gt=0, le=100000000, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: int | None = Field(default=None, ge=0, le=50)
    possession: str = Field(default="", max_length=80)
    rera_number: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=10000)
    amenities: ShortList = Field(default_factory=list)
    status: Literal["available", "off-market"] = "available"

    @model_validator(mode="after")
    def applicable_room_counts(self):
        # Full edits can include room counts from the previously selected type.
        if self.property_type not in {"apartment", "villa"}:
            self.bedrooms = None
        if self.property_type == "plot":
            self.bathrooms = None
        return self


class RequirementIn(Payload):
    purpose: Literal["buy", "rent", "invest"] = "buy"
    budget_min: Amount = Decimal(0)
    budget_max: Amount | None = None
    city: str = Field(default="", max_length=100)
    localities: ShortList = Field(default_factory=list)
    property_types: list[PropertyType] = Field(default_factory=list, max_length=7)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    timeline: str = Field(default="", max_length=100)
    financing: Literal["undecided", "self-funded", "loan-required", "loan-approved"] = "undecided"
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def budget_order(self):
        if self.budget_max is not None and self.budget_max < self.budget_min:
            raise ValueError("Maximum budget must be at least the minimum budget")
        return self


class VisitIn(Payload):
    lead_id: str
    property_id: str
    assignee_id: str | None = None
    starts_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    notes: str = Field(default="", max_length=4000)


class VisitUpdate(Payload):
    status: Literal["scheduled", "completed", "cancelled", "no-show"]
    feedback: str = Field(default="", max_length=4000)


class HandoffIn(Payload):
    lead_id: str
    executive_id: str
    property_id: str
    starts_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    brief: str = Field(min_length=3, max_length=4000)
    meeting_point: str = Field(min_length=3, max_length=500)
    client_confirmed: bool
    request_id: str = Field(min_length=8, max_length=100)


class HandoffChange(Payload):
    version: int = Field(ge=1)
    action: Literal["accept", "reschedule", "reassign", "visit_outcome", "follow_up", "cancel", "close"]
    executive_id: str | None = None
    property_id: str | None = None
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    meeting_point: str | None = Field(default=None, min_length=3, max_length=500)
    feedback: str = Field(default="", max_length=4000)
    visit_status: Literal["completed", "no-show"] | None = None
    early_visit_confirmed: bool = False
    actual_started_at: datetime | None = None
    next_step: Literal["follow_up", "ready_for_booking", "closed"] | None = None
    next_action: str = Field(default="", max_length=200)
    follow_up_at: datetime | None = None

    @model_validator(mode="after")
    def early_visit_details(self):
        if (self.early_visit_confirmed or self.actual_started_at is not None) and (
            self.action != "visit_outcome" or self.visit_status != "completed"
        ):
            raise ValueError("Only an attended visit accepts an actual early visit time")
        return self


class BookingIn(Payload):
    lead_id: str
    property_id: str
    agent_id: str
    reference: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_/-]+$")
    agreed_price: Amount
    token_amount: Amount = Decimal(0)
    commission: Amount = Decimal(0)
    booked_on: date
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def amounts(self):
        if self.agreed_price <= 0 or self.token_amount > self.agreed_price or self.commission > self.agreed_price:
            raise ValueError("Use a positive agreed price; token and commission cannot exceed it")
        return self


class BookingUpdate(Payload):
    status: Literal["reserved", "booked", "closed", "cancelled"]
    notes: str = Field(default="", max_length=4000)


class PlanIn(Payload):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1000)
    monthly_price: Decimal = Field(gt=0, le=99999999, decimal_places=2)
    yearly_price: Decimal = Field(gt=0, le=99999999, decimal_places=2)
    seats: int = Field(ge=1, le=10000)
    active: bool = True


class SubscriptionIn(Payload):
    plan_id: str | None = None
    status: Literal["trial", "active", "past-due", "cancelled"]
    cycle: Literal["monthly", "yearly"] = "monthly"
    seats: int = Field(ge=1, le=10000)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def dates(self):
        if self.ends_on < self.starts_on:
            raise ValueError("Subscription end must be on or after its start")
        if self.status == "active" and not self.plan_id:
            raise ValueError("An active subscription requires a plan")
        return self


class BillingConfigIn(Payload):
    payee_name: str = Field(default="", max_length=160)
    upi_id: str = Field(default="", max_length=160, pattern=r"^$|^[a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+$")
    instructions: str = Field(default="", max_length=2000)
    upi_enabled: bool = True
    cod_enabled: bool = False
    cod_instructions: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def payee(self):
        if self.payee_name and len(self.payee_name) < 2:
            raise ValueError("Receiving account name must have at least two characters")
        return self


class PaymentReviewIn(Payload):
    status: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=2000)
    cash_received: bool = False
