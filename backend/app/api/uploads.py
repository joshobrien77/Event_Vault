"""Upload management routes (host-facing)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

router = APIRouter()


@router.get("/{event_id}/uploads")
async def list_uploads(
    event_id: UUID,
    page: int = 1,
    per_page: int = 50,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List uploads for an event with pagination."""
    # TODO: Implement
    return {"data": [], "meta": {"page": page, "total": 0}}


@router.get("/{event_id}/uploads/stats")
async def upload_stats(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get upload statistics for an event."""
    # TODO: Implement — total count, total size, by type, by status
    return {"data": {"total_uploads": 0, "total_size_bytes": 0}}


@router.get("/{event_id}/uploads/{upload_id}")
async def get_upload(
    event_id: UUID,
    upload_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific upload."""
    # TODO: Implement
    return {"message": "get upload endpoint"}


@router.delete("/{event_id}/uploads/{upload_id}")
async def delete_upload(
    event_id: UUID,
    upload_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete an upload and its file from storage."""
    # TODO: Implement — also delete from storage backend
    return {"message": "delete upload endpoint"}
