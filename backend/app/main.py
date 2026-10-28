import json
import re
import logging
import time
from datetime import timedelta
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from . import (
    auth,
    billing,
    files,
    field_work,
    imports,
    integrations,
    leads,
    member_login,
    notification_inbox,
    organizations,
    phone_calls,
    reports,
    real_estate,
    tasks,
    workforce,
    workspace,
)
from .config import settings
from .db import SessionLocal, now
from .models import WorkerHeartbeat

log = logging.getLogger("crm.api")
app = FastAPI(
    title=f"{settings.brand_name} API",
    version="1.0.0",
    description="Organization-scoped CRM with assigned-customer Android call sync. WhatsApp is excluded.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope.get("method") not in ["POST", "PUT", "PATCH"]:
            return await self.app(scope, receive, send)
        recording_route = re.fullmatch(r"/api/leads/[0-9a-f-]{36}/files", scope.get("path", ""))
        limit = max(settings.max_upload, settings.max_recording_upload) + 1024 * 1024 if recording_route else 11 * 1024 * 1024
        count, parts = 0, []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            count += len(part)
            if count > limit:
                response = JSONResponse({"error": {"code": "body_too_large", "message": f"Request exceeds {limit // (1024 * 1024)} MiB"}}, 413)
                return await response(scope, receive, send)
            parts.append(part)
            if not message.get("more_body", False):
                break
        body, delivered = b"".join(parts), False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


app.add_middleware(BodyLimit)


@app.middleware("http")
async def request_metadata(request: Request, call_next):
    request_id = str(uuid4())
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request failed", extra={"request_id": request_id})
        response = JSONResponse(
            {
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Try again or share the request ID with support",
                },
                "request_id": request_id,
            },
            500,
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    log.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.monotonic() - start) * 1000),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_error", "message": str(exc.detail)}
    return JSONResponse({"error": detail}, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        {
            "error": {
                "code": "validation_error",
                "message": "; ".join(f"{e['field']}: {e['message']}" for e in errors),
                "fields": errors,
            }
        },
        422,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(
        {"error": {"code": "conflict", "message": "This action conflicts with another change. Refresh and try again"}},
        409,
    )


@app.get("/api/public", tags=["Public"])
def public():
    return {
        "brand": settings.brand_name,
        "email": settings.contact_email,
        "phone": settings.contact_phone,
        "business_text": settings.business_text,
        "contact_configured": bool(settings.contact_email or settings.contact_phone),
    }


@app.get("/api/health", tags=["Operations"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            heartbeat = db.get(WorkerHeartbeat, "scheduler")
            alive = bool(heartbeat and heartbeat.seen_at > now() - timedelta(seconds=90))
        return {"status": "ok" if alive else "degraded", "database": "ok", "worker": "ok" if alive else "offline"}
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable", "database": "unavailable", "worker": "unknown"}, 503)


for router in [
    auth.router,
    organizations.router,
    member_login.router,
    imports.router,
    leads.router,
    tasks.router,
    workforce.router,
    files.router,
    workspace.router,
    integrations.router,
    phone_calls.router,
    reports.router,
    notification_inbox.router,
    real_estate.router,
    billing.router,
    field_work.router,
]:
    app.include_router(router)
