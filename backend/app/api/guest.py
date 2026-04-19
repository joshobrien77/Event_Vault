"""Guest-facing routes — no authentication required."""

from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("/{short_code}")
async def resolve_event_link(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Resolve a short code to event info (name, welcome message, settings)."""
    # TODO: Implement — lookup EventLink by short_code, increment click_count
    return {"message": "resolve link endpoint"}


@router.post("/{short_code}/verify-pin")
async def verify_pin(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify guest PIN if event requires one."""
    # TODO: Implement
    return {"message": "verify pin endpoint"}


@router.post("/{short_code}/upload")
async def guest_upload(
    short_code: str,
    file: UploadFile = File(...),
    guest_name: str = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a single file as a guest.
    Validates file type/size, saves to temp, enqueues processing task.
    """
    # TODO: Implement
    # 1. Resolve short_code → event
    # 2. Validate event is active + not expired
    # 3. Validate file type (magic bytes) and size against tier limits
    # 4. Save to temp dir
    # 5. Create Upload record (status=pending)
    # 6. Enqueue Celery task: process_upload.delay(upload_id)
    # 7. Return upload_id + status
    return {"message": "upload endpoint"}


@router.post("/{short_code}/upload/chunked")
async def initiate_chunked_upload(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Initiate a chunked upload — returns upload_id and chunk parameters."""
    # TODO: Implement
    return {"message": "initiate chunked upload endpoint"}


@router.patch("/{short_code}/upload/chunked/{upload_id}")
async def upload_chunk(
    short_code: str,
    upload_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Upload a single chunk."""
    # TODO: Implement
    return {"message": "upload chunk endpoint"}


@router.post("/{short_code}/upload/chunked/{upload_id}/complete")
async def complete_chunked_upload(
    short_code: str,
    upload_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Finalize chunked upload — reassemble and enqueue processing."""
    # TODO: Implement
    return {"message": "complete chunked upload endpoint"}
