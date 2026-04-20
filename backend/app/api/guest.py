"""Guest-facing routes — no authentication required."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import magic
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError, ValidationError
from app.models.models import Event, EventLink, EventStatus, Upload, UploadStatus
from app.schemas.schemas import ChunkedUploadInit, GuestEventInfo, PinVerifyRequest, UploadResponse

router = APIRouter()

settings = get_settings()

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
    "video/webm", "video/3gpp",
}


async def _resolve_link(short_code: str, db: AsyncSession) -> tuple[EventLink, Event]:
    """Resolve a short code, verifying the link and event are active."""
    result = await db.execute(
        select(EventLink).where(EventLink.short_code == short_code, EventLink.is_active.is_(True))
    )
    link = result.scalar_one_or_none()
    if not link:
        raise AppError(404, "LINK_NOT_FOUND", "Upload link not found or has been deactivated")

    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise AppError(410, "LINK_EXPIRED", "This upload link has expired")

    result = await db.execute(
        select(Event).where(Event.id == link.event_id, Event.deleted_at.is_(None))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise AppError(404, "EVENT_NOT_FOUND", "Event not found")

    if event.status == EventStatus.ARCHIVED:
        raise AppError(410, "EVENT_ARCHIVED", "This event is no longer accepting uploads")

    if event.expires_at and event.expires_at < datetime.now(timezone.utc):
        raise AppError(410, "EVENT_EXPIRED", "This event has expired")

    return link, event


@router.get("/{short_code}", response_model=GuestEventInfo)
async def resolve_event_link(short_code: str, db: AsyncSession = Depends(get_db)):
    """Resolve a short code to event info."""
    link, event = await _resolve_link(short_code, db)

    # Increment click count
    link.click_count += 1
    await db.flush()

    return GuestEventInfo(
        event_name=event.name,
        event_type=event.event_type,
        welcome_message=event.welcome_message,
        allow_photo=event.allow_photo,
        allow_video=event.allow_video,
        upload_limit_mb=event.upload_limit_mb,
        requires_pin=event.guest_pin is not None,
    )


@router.post("/{short_code}/verify-pin", response_model=dict)
async def verify_pin(short_code: str, body: PinVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify guest PIN if event requires one."""
    _, event = await _resolve_link(short_code, db)

    if event.guest_pin is None:
        return {"valid": True}

    if body.pin != event.guest_pin:
        raise AppError(401, "INVALID_PIN", "Incorrect PIN")

    return {"valid": True}


@router.post("/{short_code}/upload", response_model=UploadResponse, status_code=201)
async def guest_upload(
    short_code: str,
    file: UploadFile = File(...),
    guest_name: str = Form(default=None),
    pin: str = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single file as a guest."""
    link, event = await _resolve_link(short_code, db)

    # PIN check
    if event.guest_pin and pin != event.guest_pin:
        raise AppError(401, "INVALID_PIN", "Incorrect PIN — upload not allowed")

    # Read file for MIME detection
    header = await file.read(2048)
    await file.seek(0)
    detected_mime = magic.from_buffer(header, mime=True)
    content_type = detected_mime or (file.content_type or "application/octet-stream")

    allowed = set()
    if event.allow_photo:
        allowed |= ALLOWED_IMAGE_TYPES
    if event.allow_video:
        allowed |= ALLOWED_VIDEO_TYPES

    if content_type not in allowed:
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", f"File type '{content_type}' is not allowed for this event")

    # Read full file to check size
    content = await file.read()
    file_size = len(content)
    limit_bytes = event.upload_limit_mb * 1024 * 1024

    if file_size > limit_bytes:
        raise AppError(413, "FILE_TOO_LARGE", f"File exceeds the {event.upload_limit_mb}MB limit")

    # Save to temp directory
    temp_dir = Path(settings.UPLOAD_TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    upload_id = uuid.uuid4()
    temp_path = temp_dir / str(upload_id)
    temp_path.write_bytes(content)

    # Create Upload record
    upload = Upload(
        id=upload_id,
        event_id=event.id,
        guest_name=guest_name,
        original_filename=file.filename or "upload",
        file_size_bytes=file_size,
        mime_type=content_type,
        status=UploadStatus.PENDING,
    )
    db.add(upload)
    await db.flush()

    # Enqueue processing task
    from app.workers.tasks import process_upload
    process_upload.delay(str(upload_id))

    return UploadResponse.model_validate(upload)


@router.post("/{short_code}/upload/chunked", response_model=dict, status_code=201)
async def initiate_chunked_upload(
    short_code: str,
    body: ChunkedUploadInit,
    db: AsyncSession = Depends(get_db),
):
    """Initiate a chunked upload — returns upload_id and chunk parameters."""
    link, event = await _resolve_link(short_code, db)

    if event.guest_pin and body.pin != event.guest_pin:
        raise AppError(401, "INVALID_PIN", "Incorrect PIN")

    allowed = set()
    if event.allow_photo:
        allowed |= ALLOWED_IMAGE_TYPES
    if event.allow_video:
        allowed |= ALLOWED_VIDEO_TYPES

    if body.mime_type not in allowed:
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", f"File type '{body.mime_type}' is not allowed")

    limit_bytes = event.upload_limit_mb * 1024 * 1024
    if body.file_size_bytes > limit_bytes:
        raise AppError(413, "FILE_TOO_LARGE", f"File exceeds the {event.upload_limit_mb}MB limit")

    upload_id = uuid.uuid4()

    # Create placeholder Upload record
    upload = Upload(
        id=upload_id,
        event_id=event.id,
        guest_name=body.guest_name,
        original_filename=body.filename,
        file_size_bytes=body.file_size_bytes,
        mime_type=body.mime_type,
        status=UploadStatus.PENDING,
    )
    db.add(upload)

    # Create chunk directory
    chunk_dir = Path(settings.UPLOAD_TEMP_DIR) / "chunks" / str(upload_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Store chunked upload metadata
    meta = {
        "total_chunks": body.total_chunks,
        "filename": body.filename,
        "mime_type": body.mime_type,
        "file_size_bytes": body.file_size_bytes,
    }
    (chunk_dir / "meta.json").write_text(json.dumps(meta))

    await db.flush()

    return {
        "upload_id": str(upload_id),
        "chunk_size_mb": settings.CHUNK_SIZE_MB,
        "total_chunks": body.total_chunks,
    }


@router.patch("/{short_code}/upload/chunked/{upload_id}", response_model=dict)
async def upload_chunk(
    short_code: str,
    upload_id: UUID,
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single chunk."""
    await _resolve_link(short_code, db)

    result = await db.execute(select(Upload).where(Upload.id == upload_id))
    if not result.scalar_one_or_none():
        raise AppError(404, "UPLOAD_NOT_FOUND", "Chunked upload session not found")

    chunk_dir = Path(settings.UPLOAD_TEMP_DIR) / "chunks" / str(upload_id)
    if not chunk_dir.exists():
        raise AppError(404, "UPLOAD_NOT_FOUND", "Chunked upload session not found")

    chunk_data = await chunk.read()
    (chunk_dir / f"chunk_{chunk_index:06d}").write_bytes(chunk_data)

    received = len(list(chunk_dir.glob("chunk_*")))
    meta = json.loads((chunk_dir / "meta.json").read_text())

    return {"chunk_index": chunk_index, "received": received, "total": meta["total_chunks"]}


@router.post("/{short_code}/upload/chunked/{upload_id}/complete", response_model=UploadResponse)
async def complete_chunked_upload(
    short_code: str,
    upload_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Finalize chunked upload — reassemble and enqueue processing."""
    await _resolve_link(short_code, db)

    result = await db.execute(select(Upload).where(Upload.id == upload_id))
    upload = result.scalar_one_or_none()
    if not upload:
        raise AppError(404, "UPLOAD_NOT_FOUND", "Chunked upload session not found")

    chunk_dir = Path(settings.UPLOAD_TEMP_DIR) / "chunks" / str(upload_id)
    if not chunk_dir.exists():
        raise AppError(404, "UPLOAD_NOT_FOUND", "Chunk data not found")

    meta = json.loads((chunk_dir / "meta.json").read_text())
    total_chunks = meta["total_chunks"]

    chunk_files = sorted(chunk_dir.glob("chunk_*"))
    if len(chunk_files) != total_chunks:
        raise AppError(
            400,
            "INCOMPLETE_UPLOAD",
            f"Expected {total_chunks} chunks, received {len(chunk_files)}",
        )

    # Reassemble
    temp_dir = Path(settings.UPLOAD_TEMP_DIR)
    temp_path = temp_dir / str(upload_id)
    with open(temp_path, "wb") as out:
        for chunk_file in chunk_files:
            out.write(chunk_file.read_bytes())

    # Cleanup chunk dir
    for f in chunk_dir.iterdir():
        f.unlink()
    chunk_dir.rmdir()

    # Enqueue processing
    from app.workers.tasks import process_upload
    process_upload.delay(str(upload_id))

    return UploadResponse.model_validate(upload)
