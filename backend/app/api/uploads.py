"""Upload management routes (host-facing)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import get_current_user_id
from app.models.models import Event, Upload, UploadStatus
from app.schemas.schemas import UploadResponse, UploadStatsResponse

router = APIRouter()


async def _get_event_or_403(event_id: UUID, user_id: UUID, db: AsyncSession) -> Event:
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.deleted_at.is_(None))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise NotFoundError("event")
    if event.user_id != user_id:
        raise ForbiddenError()
    return event


@router.get("/{event_id}/uploads", response_model=dict)
async def list_uploads(
    event_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List uploads for an event with pagination."""
    await _get_event_or_403(event_id, user_id, db)

    q = select(Upload).where(Upload.event_id == event_id)
    if status:
        try:
            q = q.where(Upload.status == UploadStatus(status))
        except ValueError:
            pass

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.order_by(Upload.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    uploads = result.scalars().all()

    return {
        "data": [UploadResponse.model_validate(u) for u in uploads],
        "meta": {"page": page, "per_page": per_page, "total": total},
    }


@router.get("/{event_id}/uploads/stats", response_model=UploadStatsResponse)
async def upload_stats(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get upload statistics for an event."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(Upload).where(Upload.event_id == event_id)
    )
    uploads = result.scalars().all()

    total_size = sum(u.file_size_bytes for u in uploads)
    photo_count = sum(1 for u in uploads if u.mime_type.startswith("image/"))
    video_count = sum(1 for u in uploads if u.mime_type.startswith("video/"))

    by_status = {s: 0 for s in UploadStatus}
    for u in uploads:
        by_status[u.status] += 1

    return UploadStatsResponse(
        total_uploads=len(uploads),
        completed_uploads=by_status[UploadStatus.COMPLETED],
        failed_uploads=by_status[UploadStatus.FAILED],
        pending_uploads=by_status[UploadStatus.PENDING],
        total_size_bytes=total_size,
        photo_count=photo_count,
        video_count=video_count,
    )


@router.get("/{event_id}/uploads/{upload_id}", response_model=UploadResponse)
async def get_upload(
    event_id: UUID,
    upload_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific upload."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.event_id == event_id)
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise NotFoundError("upload")

    return UploadResponse.model_validate(upload)


@router.delete("/{event_id}/uploads/{upload_id}", status_code=204)
async def delete_upload(
    event_id: UUID,
    upload_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete an upload and its file from storage."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.event_id == event_id)
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise NotFoundError("upload")

    # Best-effort delete from storage
    if upload.storage_path:
        try:
            from sqlalchemy.orm import selectinload
            event_result = await db.execute(
                select(Event).options(
                    selectinload(Event.storage_connection)
                ).where(Event.id == event_id)
            )
            event = event_result.scalar_one_or_none()
            if event and event.storage_connection:
                from app.services.storage_backends import get_storage_backend
                backend = get_storage_backend(event.storage_connection)
                await backend.delete_file(upload.storage_path)
        except Exception:
            pass  # Don't fail the delete if storage removal fails

    await db.delete(upload)
    await db.flush()
