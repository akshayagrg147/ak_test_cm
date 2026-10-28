"""QR payments are claims until a platform owner verifies bank receipt and approves."""

import calendar
import hashlib
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .business_schemas import BillingConfigIn, PaymentReviewIn, PlanIn, SubscriptionIn
from .common import dump, mutate, rows
from .config import settings
from .db import get_db, now
from .files import content_type, store, validate_content
from .imports import bounded_upload
from .models import (
    Attachment,
    Audit,
    CompanySubscription,
    Organization,
    PlatformBilling,
    SubscriptionPayment,
    SubscriptionPlan,
    User,
)
from .security import check_current, current, fail, lock_org, roles

router = APIRouter(prefix="/api", tags=["Company subscriptions and QR payments"])


def today():
    return now().astimezone(ZoneInfo("Asia/Kolkata")).date()


def company(db, org_id):
    org = lock_org(db, org_id)
    if not org or org.deleted:
        fail("not_found", "Company not found", 404)
    return org


def owner_check(db, ctx):
    db.refresh(ctx.session)
    db.refresh(ctx.user)
    roles(check_current(db, ctx.session), "owner")


def active_seats(db, org_id):
    return db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.org_id == org_id, User.active.is_(True), User.deleted.is_(False))
    )


def seat_limit(db, org_id):
    subscription = db.scalar(rows(db, CompanySubscription, org_id))
    if subscription and active_seats(db, org_id) >= subscription.seats:
        fail("seat_limit", "The company has used all subscription seats. Upgrade the plan or deactivate a member", 409)


def subscription_dump(db, org_id):
    item = db.scalar(rows(db, CompanySubscription, org_id))
    if not item:
        return None
    return {
        **dump(item),
        "effective_status": "expired" if item.ends_on < today() and item.status in {"trial", "active"} else item.status,
        "used_seats": active_seats(db, org_id),
    }


def billing_config(db):
    item = db.get(PlatformBilling, "default")
    return {
        "payee_name": item.payee_name if item else "",
        "upi_id": item.upi_id if item else "",
        "instructions": item.instructions if item else "",
        "qr_ready": bool(item and item.qr_storage_key and item.payee_name),
        "upi_enabled": item.upi_enabled if item else True,
        "cod_enabled": item.cod_enabled if item else False,
        "cod_instructions": item.cod_instructions if item else "",
    }


def platform_audit(db, ctx, org_id, action, summary, details=None):
    db.add(
        Audit(
            org_id=org_id,
            actor_id=ctx.id,
            entity="subscription",
            entity_id=org_id,
            action=action,
            summary=summary,
            details=details or {},
        )
    )


@router.get("/platform/billing")
def platform_billing(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    payments = []
    for payment in db.scalars(select(SubscriptionPayment).order_by(SubscriptionPayment.created_at.desc()).limit(200)):
        payments.append({**dump(payment), "company_name": db.get(Organization, payment.org_id).name})
    return {
        "config": billing_config(db),
        "plans": [dump(p) for p in db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.created_at))],
        "payments": payments,
        "pending": db.scalar(
            select(func.count()).select_from(SubscriptionPayment).where(SubscriptionPayment.status == "pending")
        ),
        "approved_amount": str(
            db.scalar(
                select(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).where(
                    SubscriptionPayment.status == "approved"
                )
            )
        ),
    }


@router.put("/platform/billing/config")
def update_config(data: BillingConfigIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    item = db.get(PlatformBilling, "default")
    if not item:
        item = PlatformBilling(id="default")
        db.add(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    db.flush()
    return billing_config(db)


@router.post("/platform/billing/qr")
async def upload_qr(file: UploadFile = File(), ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    raw = await bounded_upload(file, 5 * 1024 * 1024)
    mime = content_type(raw)
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        fail("image_required", "Upload your payment QR as a PNG, JPEG or WebP image", 422)
    validate_content(raw, mime)
    item = db.get(PlatformBilling, "default")
    if not item:
        item = PlatformBilling(id="default")
        db.add(item)
    item.qr_storage_key, item.qr_mime = store(raw), mime
    item.qr_name = Path((file.filename or "payment-qr").replace("\\", "/")).name[:200]
    db.flush()
    return billing_config(db)


@router.get("/billing/qr")
def payment_qr(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner", "admin")
    item = db.get(PlatformBilling, "default")
    if not item or not item.qr_storage_key or not (settings.storage_path / item.qr_storage_key).is_file():
        fail("qr_unavailable", "The super admin has not configured a payment QR yet", 404)
    return FileResponse(
        settings.storage_path / item.qr_storage_key,
        media_type=item.qr_mime,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


def check_plan_name(db, data, except_id=None):
    duplicate = db.scalar(select(SubscriptionPlan).where(func.lower(SubscriptionPlan.name) == data.name.lower()))
    if duplicate and duplicate.id != except_id:
        fail("duplicate_plan", "A plan with this name already exists", 409)


@router.post("/platform/plans", status_code=201)
def add_plan(data: PlanIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    check_plan_name(db, data)
    item = SubscriptionPlan(**data.model_dump())
    db.add(item)
    db.flush()
    return dump(item)


@router.put("/platform/plans/{plan_id}")
def edit_plan(plan_id: str, data: PlanIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    item = db.get(SubscriptionPlan, plan_id)
    if not item:
        fail("not_found", "Plan not found", 404)
    check_plan_name(db, data, plan_id)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    return dump(item)


@router.put("/platform/organizations/{org_id}/subscription")
def set_subscription(
    org_id: str, data: SubscriptionIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "owner")
    company(db, org_id)
    owner_check(db, ctx)
    if active_seats(db, org_id) > data.seats:
        fail("seat_limit", "Deactivate members before reducing seats below the active member count", 409)
    plan = db.get(SubscriptionPlan, data.plan_id) if data.plan_id else None
    if data.plan_id and not plan:
        fail("not_found", "Plan not found", 404)
    item = db.scalar(rows(db, CompanySubscription, org_id))
    if not item:
        item = CompanySubscription(org_id=org_id)
        db.add(item)
    for key, value in data.model_dump().items():
        setattr(item, key, value)
    item.plan_name = plan.name if plan else "Trial"
    item.amount = getattr(plan, data.cycle + "_price") if plan else 0
    platform_audit(db, ctx, org_id, "subscription_updated", "Super admin updated subscription terms")
    db.flush()
    return subscription_dump(db, org_id)


@router.get("/billing")
def company_billing(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    return {
        "subscription": subscription_dump(db, ctx.org_id),
        "config": billing_config(db),
        "plans": [
            dump(p)
            for p in db.scalars(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.active.is_(True))
                .order_by(SubscriptionPlan.monthly_price)
            )
        ],
        "payments": [
            dump(p)
            for p in db.scalars(
                rows(db, SubscriptionPayment, ctx.org_id).order_by(SubscriptionPayment.created_at.desc()).limit(100)
            )
        ],
    }


@router.post("/billing/payments", status_code=201)
async def submit_payment(
    plan_id: str = Form(),
    cycle: str = Form(),
    reference: str = Form(""),
    request_id: str = Form(),
    quoted_amount: str = Form(),
    payment_method: str = Form("upi"),
    receipt: UploadFile | None = File(None),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    roles(ctx, "admin")
    mutate(db, ctx)
    normalized_reference = reference.strip().upper() or None
    request_id = request_id.strip()
    if cycle not in {"monthly", "yearly"} or payment_method not in {"upi", "cod"} or not 8 <= len(request_id) <= 100:
        fail("invalid_payment", "Select a valid payment method, billing cycle and submission identifier", 422)
    if payment_method == "upi" and not re.fullmatch(r"[A-Z0-9/-]{4,80}", normalized_reference or ""):
        fail(
            "invalid_payment",
            "Enter a valid UPI transaction reference (4–80 letters/digits)",
            422,
        )
    if payment_method == "cod" and (normalized_reference or (receipt and receipt.filename)):
        fail(
            "invalid_cash_request",
            "Cash collection does not use a UPI reference or a company-uploaded payment receipt",
            422,
        )
    try:
        quoted = Decimal(quoted_amount)
        if not quoted.is_finite():
            fail("price_changed", "The quoted amount does not match the plan. Refresh the plan and try again", 409)
    except InvalidOperation:
        fail("invalid_amount", "The quoted plan amount is invalid", 422)
    existing = db.scalar(rows(db, SubscriptionPayment, ctx.org_id).where(SubscriptionPayment.request_id == request_id))
    if existing:
        if (existing.plan_id, existing.cycle, existing.reference, existing.payment_method, existing.amount) != (
            plan_id,
            cycle,
            normalized_reference,
            payment_method,
            quoted,
        ):
            fail("request_conflict", "This submission was already used for different payment details", 409)
        return dump(existing)
    config = billing_config(db)
    if not config[payment_method + "_enabled"]:
        fail(
            "payment_method_unavailable",
            "This payment method is unavailable. Contact the super admin or choose another method",
            409,
        )
    if payment_method == "upi" and not config["qr_ready"]:
        fail("qr_unavailable", "UPI payment instructions are not configured yet. Contact the super admin", 409)
    plan = db.get(SubscriptionPlan, plan_id)
    if not plan or not plan.active:
        fail("plan_unavailable", "Select an available subscription plan", 422)
    if quoted != getattr(plan, cycle + "_price"):
        fail(
            "price_changed",
            "The plan price changed. Refresh the plan and contact the super admin if you already paid",
            409,
        )
    if normalized_reference and db.scalar(
        select(SubscriptionPayment).where(SubscriptionPayment.reference == normalized_reference)
    ):
        fail("duplicate_reference", "This transaction reference has already been submitted", 409)
    if db.scalar(rows(db, SubscriptionPayment, ctx.org_id).where(SubscriptionPayment.status == "pending")):
        fail("payment_pending", "Your previous payment is awaiting review. Wait for the super admin to verify it", 409)
    receipt_id = None
    if receipt and receipt.filename:
        raw = await bounded_upload(receipt, 5 * 1024 * 1024)
        mime = content_type(raw)
        if mime not in {"image/png", "image/jpeg", "image/webp", "application/pdf"}:
            fail("invalid_receipt", "Upload a PNG, JPEG, WebP or PDF payment receipt", 422)
        validate_content(raw, mime)
        attachment = Attachment(
            org_id=ctx.org_id,
            author_id=ctx.id,
            name=Path(receipt.filename.replace("\\", "/")).name[:200],
            mime=mime,
            storage_key=store(raw),
            digest=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
        )
        db.add(attachment)
        db.flush()
        receipt_id = attachment.id
    item = SubscriptionPayment(
        org_id=ctx.org_id,
        plan_id=plan.id,
        submitted_by=ctx.id,
        receipt_id=receipt_id,
        plan_name=plan.name,
        seats=plan.seats,
        cycle=cycle,
        amount=getattr(plan, cycle + "_price"),
        reference=normalized_reference,
        payment_method=payment_method,
        request_id=request_id,
    )
    db.add(item)
    platform_audit(
        db,
        ctx,
        ctx.org_id,
        "payment_submitted",
        "Company requested cash collection"
        if payment_method == "cod"
        else "Company submitted a UPI payment for verification",
        {"payment_method": payment_method},
    )
    db.flush()
    return dump(item)


def period_end(start, cycle):
    month = start.month + (12 if cycle == "yearly" else 1)
    year, month = start.year + (month - 1) // 12, (month - 1) % 12 + 1
    return start.replace(year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1])) - timedelta(
        days=1
    )


@router.post("/platform/payments/{payment_id}/review")
def review_payment(
    payment_id: str, data: PaymentReviewIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")
):
    roles(ctx, "owner")
    payment = db.get(SubscriptionPayment, payment_id)
    if not payment:
        fail("not_found", "Payment not found", 404)
    company(db, payment.org_id)
    owner_check(db, ctx)
    db.refresh(payment)
    if payment.status != "pending":
        fail("already_reviewed", "This payment has already been reviewed", 409)
    if data.status == "approved":
        if payment.payment_method == "cod" and not data.cash_received:
            fail(
                "cash_confirmation_required",
                "Confirm that the cash was received before approving this subscription",
                422,
            )
        if active_seats(db, payment.org_id) > payment.seats:
            fail("seat_limit", "This plan has fewer seats than the company's active members", 409)
        subscription = db.scalar(rows(db, CompanySubscription, payment.org_id))
        start = today()
        if subscription and subscription.status == "active" and subscription.ends_on >= start:
            start = subscription.ends_on + timedelta(days=1)
        if not subscription:
            subscription = CompanySubscription(org_id=payment.org_id, starts_on=today())
            db.add(subscription)
        elif subscription.status != "active" or subscription.ends_on < today():
            subscription.starts_on = today()
        subscription.plan_id, subscription.plan_name = payment.plan_id, payment.plan_name
        subscription.cycle, subscription.amount, subscription.seats = payment.cycle, payment.amount, payment.seats
        subscription.status, subscription.ends_on = "active", period_end(start, payment.cycle)
    payment.status, payment.review_note = data.status, data.note
    payment.reviewed_by, payment.reviewed_at = ctx.id, now()
    platform_audit(
        db,
        ctx,
        payment.org_id,
        "payment_" + data.status,
        "Super admin " + data.status + " subscription payment",
        {
            "payment_id": payment.id,
            "payment_method": payment.payment_method,
            "cash_received": data.cash_received
            if payment.payment_method == "cod" and data.status == "approved"
            else False,
        },
    )
    return dump(payment)


@router.get("/platform/payments/{payment_id}/receipt")
def platform_receipt(payment_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "owner")
    payment = db.get(SubscriptionPayment, payment_id)
    item = db.get(Attachment, payment.receipt_id) if payment and payment.receipt_id else None
    if not item or not (settings.storage_path / item.storage_key).is_file():
        fail("not_found", "Receipt not found", 404)
    return FileResponse(
        settings.storage_path / item.storage_key,
        media_type=item.mime,
        filename=item.name,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
