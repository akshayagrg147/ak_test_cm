"""Public property share links: one unauthenticated page per shared property.

Security model:
- The URL token is 128 random bits. Only its SHA-256 is used for lookup; an encrypted copy lets
  the broker copy the same link again. Neither is ever serialized.
- Public JSON and HTML are built from an explicit allow-list; the model is never dumped.
- Photos and PDFs are served only when ticked, by position (not file id), after re-checking that
  the link is on, the company active and the property still available.
- Every public route is rate-limited per visitor IP and never stores the raw IP.
"""

import hashlib
import html
import io
import json
import secrets
from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from PIL import Image
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .common import audit, get_scoped, lead_access, mutate, rows
from .config import settings
from .db import get_db, now
from .models import Attachment, LoginGuard, Note, Organization, Property, PropertyShare, PropertyShareView, User
from .schemas import Payload
from .security import current, decrypt, encrypt, fail, roles, workspace

router = APIRouter(tags=["Property sharing"])
PUBLIC_LIMIT = 60  # requests per visitor per minute across all public share routes
MAX_PHOTO_EDGE = 1600
UNAVAILABLE = {"reserved", "sold", "leased", "off-market"}
SECURITY_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'",
}


class ShareIn(Payload):
    photo_file_ids: list[str] | None = Field(default=None, max_length=50)
    doc_file_ids: list[str] = Field(default_factory=list, max_length=20)
    show_rera: bool = True
    contact_mode: Literal["sharer", "company"] = "sharer"


class ShareSettingsIn(Payload):
    callers_can_share: bool


class ShareLogIn(Payload):
    property_id: str = Field(min_length=1, max_length=36)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def share_url(token):
    return settings.public_origin.rstrip("/") + "/p/" + token


def active_share(db, org_id, property_id):
    return db.scalar(
        rows(db, PropertyShare, org_id).where(PropertyShare.property_id == property_id, PropertyShare.enabled.is_(True))
    )


def share_link_for(db, org_id, property_id):
    """Current public link for a property, or "" (used by templates' {{property_link}} and matches)."""
    item = active_share(db, org_id, property_id)
    return share_url(decrypt(item.token_enc)) if item else ""


def property_files(db, prop, pdf=False):
    query = rows(db, Attachment, prop.org_id).where(Attachment.property_id == prop.id)
    query = query.where(Attachment.mime == "application/pdf") if pdf else query.where(Attachment.mime.like("image/%"))
    return list(db.scalars(query.order_by(Attachment.created_at, Attachment.id)))


def can_publish(ctx):
    if ctx.role in {"admin", "manager"}:
        return True
    return ctx.role == "telecaller" and bool(ctx.org.settings.get("callers_can_share", False))


def share_state(db, ctx, prop):
    item = active_share(db, ctx.org_id, prop.id)
    photos, docs = property_files(db, prop), property_files(db, prop, pdf=True)
    return {
        "enabled": bool(item),
        "url": share_url(decrypt(item.token_enc)) if item else None,
        "photo_file_ids": item.photo_file_ids if item else None,
        "doc_file_ids": item.doc_file_ids if item else [],
        "show_rera": item.show_rera if item else True,
        "contact_mode": item.contact_mode if item else "sharer",
        "views": item.views if item else 0,
        "last_viewed_at": item.last_viewed_at if item else None,
        "available": not prop.archived and prop.status == "available",
        "can_manage": can_publish(ctx),
        "callers_can_share": bool(ctx.org.settings.get("callers_can_share", False)),
        "photos": [{"id": f.id, "name": f.name} for f in photos],
        "documents": [{"id": f.id, "name": f.name} for f in docs],
    }


@router.get("/api/properties/{property_id}/share")
def get_share(property_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    return share_state(db, ctx, get_scoped(db, Property, property_id, ctx))


def _validate_files(db, prop, data):
    photo_ids = {f.id for f in property_files(db, prop)}
    doc_ids = {f.id for f in property_files(db, prop, pdf=True)}
    if data.photo_file_ids is not None and not set(data.photo_file_ids) <= photo_ids:
        fail("invalid_file", "Pick photos of this property only", 422)
    if not set(data.doc_file_ids) <= doc_ids:
        fail("invalid_file", "Pick PDF brochures or floor plans of this property only", 422)


@router.put("/api/properties/{property_id}/share")
def save_share(property_id: str, data: ShareIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    mutate(db, ctx)
    if not can_publish(ctx):
        fail("permission_denied", "Only an admin or manager can make a property public", 403)
    prop = get_scoped(db, Property, property_id, ctx)
    if prop.archived or prop.status != "available":
        fail("property_unavailable", "Only available properties can be shared", 409)
    _validate_files(db, prop, data)
    item = active_share(db, ctx.org_id, prop.id)
    created = item is None
    if created:
        token = secrets.token_urlsafe(16)
        item = PropertyShare(org_id=ctx.org_id, property_id=prop.id, token_hash=token_hash(token),
                             token_enc=encrypt(token), created_by=ctx.id)
        db.add(item)
    item.photo_file_ids = list(dict.fromkeys(data.photo_file_ids)) if data.photo_file_ids is not None else None
    item.doc_file_ids = list(dict.fromkeys(data.doc_file_ids))
    item.show_rera, item.contact_mode = data.show_rera, data.contact_mode
    db.flush()
    audit(db, ctx, "property", prop.id, "share_enabled" if created else "share_updated",
          f"{'Turned on' if created else 'Updated'} the public link for {prop.reference}; link redacted")
    return share_state(db, ctx, prop)


@router.post("/api/properties/{property_id}/share/replace")
def replace_share(property_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    mutate(db, ctx)
    if not can_publish(ctx):
        fail("permission_denied", "Only an admin or manager can replace a public link", 403)
    prop = get_scoped(db, Property, property_id, ctx)
    item = active_share(db, ctx.org_id, prop.id)
    if not item:
        fail("not_shared", "Turn on sharing first", 409)
    token = secrets.token_urlsafe(16)
    item.token_hash, item.token_enc, item.views, item.last_viewed_at = token_hash(token), encrypt(token), 0, None
    audit(db, ctx, "property", prop.id, "share_replaced", f"Replaced the public link for {prop.reference}; old link stopped")
    return share_state(db, ctx, prop)


@router.delete("/api/properties/{property_id}/share")
def disable_share(property_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    workspace(ctx)
    mutate(db, ctx)
    if not can_publish(ctx):
        fail("permission_denied", "Only an admin or manager can turn off a public link", 403)
    prop = get_scoped(db, Property, property_id, ctx)
    item = active_share(db, ctx.org_id, prop.id)
    if item:
        item.enabled, item.revoked_at = False, now()
        # The stored token is no longer needed; keep only the hash for history.
        item.token_enc = encrypt(secrets.token_urlsafe(16))
        audit(db, ctx, "property", prop.id, "share_disabled", f"Turned off the public link for {prop.reference}")
    return share_state(db, ctx, prop)


@router.put("/api/property-share-settings")
def share_settings(data: ShareSettingsIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    ctx.org.settings = {**ctx.org.settings, "callers_can_share": data.callers_can_share}
    audit(db, ctx, "organization", ctx.org_id, "share_settings_updated",
          ("Allowed" if data.callers_can_share else "Stopped") + " telecallers making properties public")
    return {"callers_can_share": data.callers_can_share}


@router.post("/api/leads/{lead_id}/property-share-log", status_code=201)
def log_share(lead_id: str, data: ShareLogIn, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    """Record that a user opened WhatsApp to send a property link; ViaCRM does not send it."""
    mutate(db, ctx)
    lead = lead_access(db, ctx, lead_id)
    if lead.dnd:
        fail("do_not_contact", "Client is marked do-not-contact", 409)
    prop = get_scoped(db, Property, data.property_id, ctx)
    item = active_share(db, ctx.org_id, prop.id)
    if not item or prop.archived or prop.status != "available":
        fail("not_shared", "This property has no public link", 404)
    text = f"Shared property {prop.title} link on WhatsApp (opened)"
    db.add(Note(org_id=ctx.org_id, lead_id=lead.id, author_id=ctx.id, text=text))
    audit(db, ctx, "lead", lead.id, "property_shared", text, {"property_id": prop.id})
    return {"ok": True, "url": share_url(decrypt(item.token_enc))}


# ----------------------------------------------------------------------------------------- public


def visitor_ip(request: Request):
    # Caddy (the trusted edge) sets X-Forwarded-For; nginx passes it through unchanged.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def rate_limit(db, request):
    key = hashlib.sha256(("share:" + visitor_ip(request)).encode()).hexdigest()
    db.execute(insert(LoginGuard).values(key=key, attempts=0, window=now()).on_conflict_do_nothing())
    guard = db.scalar(select(LoginGuard).where(LoginGuard.key == key).with_for_update())
    if guard.window < now() - timedelta(minutes=1):
        guard.attempts, guard.window = 0, now()
    guard.attempts += 1
    db.commit()
    if guard.attempts > PUBLIC_LIMIT:
        fail("rate_limited", "Too many requests. Please wait a minute and try again", 429)


def resolve(db, token):
    """(share, org, property, available) for an enabled link of an active company, or None."""
    if not token or len(token) > 64:
        return None
    item = db.scalar(select(PropertyShare).where(PropertyShare.token_hash == token_hash(token),
                                                 PropertyShare.enabled.is_(True)))
    if not item:
        return None
    org = db.get(Organization, item.org_id)
    prop = db.get(Property, item.property_id)
    if not org or not org.active or org.deleted or not prop or prop.org_id != org.id:
        return None
    return item, org, prop, not prop.archived and prop.status == "available"


def indian_money(value):
    amount = Decimal(value or 0)
    if amount >= 10_000_000:
        return "₹" + f"{amount / 10_000_000:.2f}".rstrip("0").rstrip(".") + " Cr"
    if amount >= 100_000:
        return "₹" + f"{amount / 100_000:.2f}".rstrip("0").rstrip(".") + " L"
    whole = f"{int(amount):,}"
    return "₹" + whole


def contact(db, item, org):
    profile = org.settings.get("company_profile") or {}
    company = {"name": org.settings.get("brand_name") or org.name, "phone": profile.get("phone") or ""}
    if item.contact_mode == "sharer" and item.created_by:
        user = db.get(User, item.created_by)
        if user and user.active and not user.deleted and user.org_id == org.id:
            return {"name": user.name, "phone": user.phone}
    return company


def wa_digits(phone):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit()).lstrip("0")
    if len(digits) == 10:
        digits = "91" + digits
    return digits if 11 <= len(digits) <= 15 else ""


def public_photos(db, item, prop):
    photos = property_files(db, prop)
    if item.photo_file_ids is None:
        return photos
    ticked = set(item.photo_file_ids)
    return [f for f in photos if f.id in ticked]


def public_docs(db, item, prop):
    ticked = set(item.doc_file_ids or [])
    return [f for f in property_files(db, prop, pdf=True) if f.id in ticked]


def public_payload(db, token, item, org, prop, available):
    """Allow-listed public fields only. Never ids, reference, address, owner/developer or file ids."""
    who = contact(db, item, org)
    base = {
        "company": {"name": org.settings.get("brand_name") or org.name},
        "contact": {"name": who["name"], "phone": who["phone"]},
        "available": available,
    }
    if not available:
        return base
    return {
        **base,
        "title": prop.title,
        "price": indian_money(prop.price),
        "listing_type": prop.listing_type,
        "property_type": prop.property_type,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "area_sqft": str(prop.area_sqft),
        "locality": prop.locality,
        "city": prop.city,
        "possession": prop.possession,
        "amenities": list(prop.amenities or []),
        "description": prop.description,
        "rera_number": prop.rera_number if item.show_rera else "",
        "photos": [f"/api/public/p/{quote(token)}/photo/{n}" for n in range(len(public_photos(db, item, prop)))],
        "documents": [{"name": f.name, "url": f"/api/public/p/{quote(token)}/doc/{n}"}
                      for n, f in enumerate(public_docs(db, item, prop))],
    }


def not_found_page():
    page = ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<meta name=robots content='noindex,nofollow'><title>Link not available</title>"
            "<body style='font:16px system-ui,sans-serif;margin:40px 20px;color:#1f2937'>"
            "<h1 style='font-size:22px'>This link is not available</h1>"
            "<p>The link may have been turned off. Please ask the person who shared it for a new one.</p></body></html>")
    return HTMLResponse(page, status_code=404, headers=SECURITY_HEADERS)


@router.get("/api/public/p/{token}")
def public_json(token: str, request: Request, db: Session = Depends(get_db, scope="function")):
    rate_limit(db, request)
    found = resolve(db, token)
    if not found:
        fail("not_found", "This link is not available", 404)
    return Response(
        content=json.dumps(public_payload(db, token, *found), default=str),
        media_type="application/json",
        headers={**SECURITY_HEADERS, "Cache-Control": "no-store"},
    )


_resized: "OrderedDict[str, bytes]" = OrderedDict()


def resized(path, key):
    if key in _resized:
        _resized.move_to_end(key)
        return _resized[key]
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=82, optimize=True)
    data = out.getvalue()
    _resized[key] = data
    while len(_resized) > 64:
        _resized.popitem(last=False)
    return data


def _file_or_404(db, token, request, pick):
    rate_limit(db, request)
    found = resolve(db, token)
    if not found or not found[3]:
        fail("not_found", "This link is not available", 404)
    item, _org, prop, _available = found
    record = pick(item, prop)
    path = settings.storage_path / record.storage_key if record else None
    if not record or not path.is_file():
        fail("not_found", "This file is not available", 404)
    return record, path


@router.get("/api/public/p/{token}/photo/{n}")
def public_photo(token: str, n: int, request: Request, db: Session = Depends(get_db, scope="function")):
    def pick(item, prop):
        photos = public_photos(db, item, prop)
        return photos[n] if 0 <= n < len(photos) else None

    record, path = _file_or_404(db, token, request, pick)
    return Response(resized(path, record.id), media_type="image/jpeg",
                    headers={**SECURITY_HEADERS, "Cache-Control": "public, max-age=300"})


@router.get("/api/public/p/{token}/doc/{n}")
def public_doc(token: str, n: int, request: Request, db: Session = Depends(get_db, scope="function")):
    def pick(item, prop):
        docs = public_docs(db, item, prop)
        return docs[n] if 0 <= n < len(docs) else None

    record, path = _file_or_404(db, token, request, pick)
    name = quote(record.name)
    return Response(path.read_bytes(), media_type="application/pdf",
                    headers={**SECURITY_HEADERS, "Cache-Control": "private, max-age=300",
                             "Content-Disposition": f"attachment; filename*=UTF-8''{name}"})


def count_view(db, item, request):
    visitor = hashlib.sha256((item.id + ":" + visitor_ip(request)).encode()).hexdigest()
    inserted = db.execute(
        insert(PropertyShareView).values(share_id=item.id, day=now().date(), visitor=visitor).on_conflict_do_nothing()
    ).rowcount
    if inserted:
        item.views += 1
    item.last_viewed_at = now()


@router.get("/p/{token}", response_class=HTMLResponse, include_in_schema=False)
def public_page(token: str, request: Request, db: Session = Depends(get_db, scope="function")):
    """Standalone, script-free page so WhatsApp can build a preview card from its meta tags."""
    rate_limit(db, request)
    found = resolve(db, token)
    if not found:
        return not_found_page()
    item, org, prop, available = found
    count_view(db, item, request)
    data = public_payload(db, token, *found)
    e = html.escape
    who = data["contact"]
    link = share_url(token)
    buttons = ""
    if who["phone"]:
        wa = wa_digits(who["phone"])
        ask = f"Hi, I saw {prop.title} ({link}). Is it available?" if available else f"Hi, I'm looking for options like {prop.title}."
        buttons = (f"<a class=btn href='tel:{e(who['phone'])}'>Call {e(who['name'])}</a>"
                   + (f"<a class='btn wa' href='https://wa.me/{wa}?text={quote(ask)}' rel='noopener noreferrer'>"
                      f"WhatsApp {e(who['name'])}</a>" if wa else ""))
    company = e(data["company"]["name"])
    if not available:
        body = (f"<h1>This property is no longer available</h1><p>Contact {e(who['name'])} for similar options.</p>"
                f"<div class=actions>{buttons}</div>")
        title, description, image = "Property no longer available", f"Contact {who['name']} for similar options.", ""
    else:
        specs = [data["property_type"].title(), "For rent" if data["listing_type"] == "rent" else "For sale"]
        if data["bedrooms"]:
            specs.append(f"{data['bedrooms']} BHK")
        if data["bathrooms"]:
            specs.append(f"{data['bathrooms']} baths")
        specs.append(f"{Decimal(data['area_sqft']):,.0f} sq ft")
        place = ", ".join(v for v in [data["locality"], data["city"]] if v)
        photos = "".join(f"<img src='{e(src)}' alt='{e(prop.title)} photo {i + 1}' loading='lazy'>"
                         for i, src in enumerate(data["photos"])) or "<div class=placeholder>Photos coming soon</div>"
        docs = "".join(f"<li><a href='{e(d['url'])}'>{e(d['name'])}</a></li>" for d in data["documents"])
        amenities = "".join(f"<li>{e(a)}</li>" for a in data["amenities"])
        body = (
            f"<div class=gallery>{photos}</div>"
            f"<h1>{e(prop.title)}</h1><p class=price>{e(data['price'])}"
            f"{' / month' if data['listing_type'] == 'rent' else ''}</p>"
            f"<p class=place>{e(place)}</p><p class=specs>{e(' · '.join(specs))}</p>"
            f"<div class=actions>{buttons}</div>"
            + (f"<p><b>Possession:</b> {e(data['possession'])}</p>" if data["possession"] else "")
            + (f"<h2>Amenities</h2><ul class=chips>{amenities}</ul>" if amenities else "")
            + (f"<h2>About</h2><p class=desc>{e(data['description'])}</p>" if data["description"] else "")
            + (f"<h2>Brochures</h2><ul>{docs}</ul>" if docs else "")
            + (f"<p class=muted>RERA: {e(data['rera_number'])}</p>" if data["rera_number"] else "")
        )
        title = f"{prop.title} · {data['price']}"
        description = " · ".join([place, *specs])
        image = settings.public_origin.rstrip("/") + data["photos"][0] if data["photos"] else ""
    meta = (f"<meta property='og:title' content='{e(title)}'><meta property='og:description' content='{e(description)}'>"
            f"<meta property='og:type' content='website'><meta property='og:url' content='{e(link)}'>"
            f"<meta property='og:site_name' content='{company}'>"
            + (f"<meta property='og:image' content='{e(image)}'>" if image else ""))
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'><meta name=robots content='noindex,nofollow'>
<meta name=referrer content=no-referrer><title>{e(title)}</title>{meta}
<style>
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937;background:#f6f7fb}}
header{{background:#fff;padding:14px 16px;border-bottom:1px solid #e5e7eb;font-weight:700;color:#264edb}}
main{{max-width:720px;margin:0 auto;padding:16px}}
.gallery{{display:flex;gap:8px;overflow-x:auto;scroll-snap-type:x mandatory;border-radius:12px}}
.gallery img{{flex:0 0 100%;width:100%;aspect-ratio:4/3;object-fit:cover;scroll-snap-align:center;border-radius:12px;background:#e5e7eb}}
.placeholder{{width:100%;aspect-ratio:4/3;display:grid;place-items:center;background:#e5e7eb;border-radius:12px;color:#4b5563}}
h1{{font-size:22px;margin:16px 0 4px;overflow-wrap:anywhere}}h2{{font-size:17px;margin:20px 0 6px}}
.price{{font-size:24px;font-weight:700;margin:0;color:#111827}}.place,.specs{{margin:2px 0;color:#4b5563}}
.actions{{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}}
.btn{{flex:1 1 140px;text-align:center;padding:12px 14px;border-radius:10px;background:#264edb;color:#fff;text-decoration:none;font-weight:600}}
.btn.wa{{background:#0b5d33}}.chips{{display:flex;flex-wrap:wrap;gap:6px;padding:0;list-style:none}}
.chips li{{background:#fff;border:1px solid #e5e7eb;border-radius:999px;padding:3px 10px;font-size:14px}}
.desc{{white-space:pre-line;overflow-wrap:anywhere}}.muted{{color:#4b5563;font-size:14px}}
footer{{text-align:center;color:#6b7280;font-size:13px;padding:24px 16px}}
</style></head><body><header>{company}</header><main>{body}</main>
<footer>Shared by {company} using ViaCRM</footer></body></html>"""
    return HTMLResponse(page, headers={**SECURITY_HEADERS, "Cache-Control": "no-store"})
