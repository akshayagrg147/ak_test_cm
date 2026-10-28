import hashlib
import io
from pathlib import Path

import mutagen
from mutagen.mp4 import MP4
from PIL import Image
from pypdf import PdfReader

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .common import audit, dump, get_scoped, lead_access, mutate, rows
from .config import settings
from .db import get_db, uid
from .imports import bounded_upload
from .models import Attachment, Note, PhoneCall
from .security import current, fail, roles

router = APIRouter(prefix="/api", tags=["Private files"])


def store(raw):
    key = uid()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    path = settings.storage_path / key
    path.write_bytes(raw)
    path.chmod(0o600)
    return key


def content_type(raw):
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return "audio/wav"
    if raw.startswith(b"OggS"):
        return "audio/ogg"
    if raw.startswith(b"fLaC"):
        return "audio/flac"
    if raw.startswith(b"ID3") or (len(raw) > 2 and raw[0] == 255 and raw[1] & 224 == 224):
        return "audio/mpeg"
    # Phone dialers also use compatible ISO media brands such as 3gp4 and mp41.
    # validate_content must still parse a real audio stream before accepting it.
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return "audio/mp4"
    fail(
        "unsupported_content",
        "Upload a PDF, PNG, JPEG, WebP, MP3, M4A, WAV, OGG or FLAC file with valid file content",
        422,
    )


def mp4_audio(raw):
    # Some dialers use unversioned QuickTime metadata, which Mutagen can read
    # past and miss the following audio track. Ignore non-audio metadata in a
    # parser-only copy, preserving every box offset and the original upload.
    inspected = bytearray(raw)
    pending = [(0, len(raw), 0)]
    count = 0
    while pending:
        position, end, depth = pending.pop()
        while position < end:
            count += 1
            if count > 10000 or end - position < 8:
                raise ValueError()
            size = int.from_bytes(raw[position:position + 4], "big")
            kind = raw[position + 4:position + 8]
            header = 8
            if size == 1:
                if end - position < 16:
                    raise ValueError()
                size = int.from_bytes(raw[position + 8:position + 16], "big")
                header = 16
            elif size == 0:
                size = end - position
            if size < header or position + size > end:
                raise ValueError()
            if kind in {b"meta", b"udta"}:
                inspected[position + 4:position + 8] = b"free"
            elif kind in {b"moov", b"trak", b"mdia", b"minf", b"stbl"}:
                if depth >= 12:
                    raise ValueError()
                pending.append((position + header, position + size, depth + 1))
            position += size
    return MP4(io.BytesIO(inspected))


def validate_content(raw, mime):
    try:
        if mime.startswith("image/"):
            with Image.open(io.BytesIO(raw), formats=["PNG", "JPEG", "WEBP"]) as image:
                if image.width * image.height > 20_000_000:
                    raise ValueError()
                image.verify()
        elif mime == "application/pdf":
            with PdfReader(io.BytesIO(raw), strict=True) as document:
                if "/Root" not in document.trailer:
                    raise ValueError()
                # Password-protected documents remain private downloadable files.
                # Their cross-reference/trailer can be checked without decrypting.
                if not document.is_encrypted and not 1 <= len(document.pages) <= 10000:
                    raise ValueError()
        elif mime.startswith("audio/"):
            media = mp4_audio(raw) if mime == "audio/mp4" else mutagen.File(io.BytesIO(raw))
            if media is None or not media.info or not 0 < media.info.length <= 86400:
                raise ValueError()
            # MP4 can expose a movie duration even when there is no audio track.
            if mime == "audio/mp4" and (
                not getattr(media.info, "codec", "")
                or getattr(media.info, "channels", 0) <= 0
                or getattr(media.info, "sample_rate", 0) <= 0
            ):
                raise ValueError()
    except Exception:
        fail("invalid_content", "The file content is corrupt, incomplete or exceeds supported media limits", 422)


@router.post("/leads/{lead_id}/files", status_code=201)
async def upload(
    lead_id: str,
    file: UploadFile = File(),
    phone_call_id: str | None = Form(None),
    note_id: str | None = Form(None),
    ctx=Depends(current),
    db: Session = Depends(get_db, scope="function"),
):
    mutate(db, ctx)
    lead_access(db, ctx, lead_id)
    raw = await bounded_upload(file, settings.max_recording_upload if phone_call_id else settings.max_upload)
    mime = content_type(raw)
    validate_content(raw, mime)
    call = None
    if phone_call_id:
        call = get_scoped(db, PhoneCall, phone_call_id, ctx)
        if call.lead_id != lead_id or (ctx.role in {"telecaller", "field_executive"} and call.user_id != ctx.id):
            fail("invalid_call", "Choose an accessible call on this lead", 422)
        if not mime.startswith("audio/"):
            fail("audio_required", "A recording must contain supported audio", 422)
    if note_id:
        note = get_scoped(db, Note, note_id, ctx)
        if note.lead_id != lead_id:
            fail("invalid_note", "Choose a note on this lead", 422)
    digest = hashlib.sha256(raw).hexdigest()
    duplicate = db.scalar(
        rows(db, Attachment, ctx.org_id).where(
            Attachment.lead_id == lead_id, Attachment.phone_call_id == phone_call_id, Attachment.digest == digest
        )
    )
    if duplicate:
        return dump(duplicate)
    # One audio file must not silently attach to multiple unrelated calls.
    if call and db.scalar(
        rows(db, Attachment, ctx.org_id).where(
            Attachment.digest == digest, Attachment.phone_call_id.is_not(None), Attachment.phone_call_id != call.id
        )
    ):
        fail("recording_reused", "This recording is already attached to a different call", 409)
    name = Path((file.filename or "document").replace("\\", "/")).name[:200]
    record = Attachment(
        org_id=ctx.org_id,
        lead_id=lead_id,
        note_id=note_id,
        phone_call_id=phone_call_id,
        author_id=ctx.id,
        name=name,
        mime=mime,
        storage_key=store(raw),
        digest=digest,
        size=len(raw),
    )
    db.add(record)
    db.flush()
    if call:
        call.recording_state = "attached"
    audit(
        db,
        ctx,
        "lead",
        lead_id,
        "file_added",
        "Private file attached",
        {"attachment_id": record.id, "name": record.name},
    )
    return dump(record)


def file_access(db, ctx, file_id):
    record = get_scoped(db, Attachment, file_id, ctx)
    if record.lead_id:
        lead_access(db, ctx, record.lead_id)
    elif record.property_id:
        from .real_estate import property_record

        property_record(db, ctx, record.property_id)
    elif ctx.role != "admin" and ctx.org.settings.get("logo_id") != record.id:
        fail("permission_denied", "Organization files require administrator access", 403)
    if record.phone_call_id and ctx.role == "telecaller":
        call = get_scoped(db, PhoneCall, record.phone_call_id, ctx)
        if call.user_id != ctx.id:
            fail("not_found", "Recording not available", 404)
    return record


@router.get("/files/{file_id}")
def download(file_id: str, inline: bool = False, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    record = file_access(db, ctx, file_id)
    path = settings.storage_path / record.storage_key
    if not path.is_file():
        fail("file_unavailable", "The stored file is unavailable. Contact your administrator", 404)
    return FileResponse(
        path,
        media_type=record.mime,
        filename=record.name,
        content_disposition_type="inline" if inline and record.mime.startswith("audio/") else "attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.delete("/files/{file_id}")
def delete_file(file_id: str, ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    mutate(db, ctx)
    record = file_access(db, ctx, file_id)
    if ctx.role in {"telecaller", "field_executive"} and (record.phone_call_id or record.mime.startswith("audio/")):
        fail("recording_delete_forbidden", "Telecallers cannot delete recordings. Contact an administrator", 403)
    from .models import SubscriptionPayment

    if db.scalar(rows(db, SubscriptionPayment, ctx.org_id).where(SubscriptionPayment.receipt_id == record.id)):
        fail("receipt_in_use", "Payment receipts are retained with the payment history", 409)
    if record.author_id != ctx.id and ctx.role != "admin":
        fail("permission_denied", "Only the uploader or an administrator may remove a file", 403)
    call_id = record.phone_call_id
    if ctx.org.settings.get("logo_id") == record.id:
        ctx.org.settings = {k: v for k, v in ctx.org.settings.items() if k != "logo_id"}
    db.delete(record)
    db.flush()
    if call_id:
        call = db.get(PhoneCall, call_id)
        if not db.scalar(select(Attachment).where(Attachment.phone_call_id == call_id)):
            call.recording_state = "unavailable"
    # Files are retained until the operator's orphan-storage collection, after database backup retention.
    return {"ok": True}


@router.post("/properties/{property_id}/files", status_code=201)
async def property_file(property_id: str, file: UploadFile = File(), ctx=Depends(current),
                        db: Session = Depends(get_db, scope="function")):
    from .real_estate import property_record

    roles(ctx, "admin", "manager")
    mutate(db, ctx)
    property_record(db, ctx, property_id)
    raw = await bounded_upload(file, settings.max_upload)
    mime = content_type(raw)
    if mime not in {"image/png", "image/jpeg", "image/webp", "application/pdf"}:
        fail("property_file_required", "Upload a property photo (PNG, JPEG, WebP) or PDF brochure", 422)
    validate_content(raw, mime)
    digest = hashlib.sha256(raw).hexdigest()
    existing = db.scalar(rows(db, Attachment, ctx.org_id).where(Attachment.property_id == property_id, Attachment.digest == digest))
    if existing:
        return dump(existing)
    item = Attachment(org_id=ctx.org_id, property_id=property_id, author_id=ctx.id,
                      name=Path((file.filename or "property-file").replace("\\", "/")).name[:200],
                      mime=mime, storage_key=store(raw), size=len(raw), digest=digest)
    db.add(item)
    db.flush()
    audit(db, ctx, "property", property_id, "file_added", "Added property photo or brochure", {"attachment_id": item.id})
    return dump(item)


@router.post("/settings/logo")
async def logo(file: UploadFile = File(), ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    raw = await bounded_upload(file)
    mime = content_type(raw)
    validate_content(raw, mime)
    if mime not in ["image/png", "image/jpeg", "image/webp"]:
        fail("image_required", "Upload a PNG, JPEG or WebP logo; transparent PNG/WebP is preserved", 422)
    record = Attachment(
        org_id=ctx.org_id,
        author_id=ctx.id,
        name="organization-logo",
        mime=mime,
        storage_key=store(raw),
        digest=hashlib.sha256(raw).hexdigest(),
        size=len(raw),
    )
    db.add(record)
    db.flush()
    ctx.org.settings = {**ctx.org.settings, "logo_id": record.id}
    return dump(record)


@router.delete("/settings/logo")
def remove_logo(ctx=Depends(current), db: Session = Depends(get_db, scope="function")):
    roles(ctx, "admin")
    mutate(db, ctx)
    ctx.org.settings = {k: v for k, v in ctx.org.settings.items() if k != "logo_id"}
    return {"ok": True}
