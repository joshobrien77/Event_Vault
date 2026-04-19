"""Storage connection routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

router = APIRouter()


@router.get("/{event_id}/storage")
async def get_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get storage configuration for an event."""
    # TODO: Implement
    return {"message": "get storage endpoint"}


@router.put("/{event_id}/storage")
async def set_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set or update storage configuration (Dropbox or S3 credentials)."""
    # TODO: Implement — encrypt credentials before storing
    return {"message": "set storage endpoint"}


@router.post("/{event_id}/storage/verify")
async def verify_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Test storage connection by uploading a small test file."""
    # TODO: Implement
    return {"message": "verify storage endpoint"}


@router.post("/{event_id}/storage/managed")
async def provision_managed_s3(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Provision a managed S3 bucket for the event."""
    # TODO: Implement — boto3 create_bucket, set CORS, store config
    return {"message": "provision managed s3 endpoint"}


@router.delete("/{event_id}/storage")
async def remove_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove storage configuration."""
    # TODO: Implement
    return {"message": "remove storage endpoint"}
