"""Storage connection routes."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import encrypt_credentials, get_current_user_id
from app.models.models import Event, StorageConnection, StorageType
from app.schemas.schemas import ManagedS3Request, StorageResponse, StorageSetup

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


@router.get("/{event_id}/storage", response_model=StorageResponse)
async def get_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get storage configuration for an event."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(StorageConnection).where(StorageConnection.event_id == event_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise NotFoundError("storage configuration")

    return StorageResponse.model_validate(conn)


@router.put("/{event_id}/storage", response_model=StorageResponse)
async def set_storage(
    event_id: UUID,
    body: StorageSetup,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set or update storage configuration (Dropbox or S3 credentials)."""
    await _get_event_or_403(event_id, user_id, db)

    # Build and encrypt credentials payload
    if body.storage_type == StorageType.S3:
        if not body.aws_access_key_id or not body.aws_secret_access_key or not body.bucket_name:
            raise ValidationError("S3 requires aws_access_key_id, aws_secret_access_key, and bucket_name")
        creds = json.dumps({
            "aws_access_key_id": body.aws_access_key_id,
            "aws_secret_access_key": body.aws_secret_access_key,
        })
        bucket_name = body.bucket_name
        bucket_region = body.bucket_region or "us-east-1"
        folder_path = None

    elif body.storage_type == StorageType.DROPBOX:
        if not body.dropbox_access_token:
            raise ValidationError("Dropbox requires dropbox_access_token")
        creds = json.dumps({
            "access_token": body.dropbox_access_token,
            "refresh_token": body.dropbox_refresh_token,
        })
        bucket_name = None
        bucket_region = None
        folder_path = body.dropbox_folder_path or "/EventVault"

    else:
        raise ValidationError("Use POST /storage/managed to provision a managed S3 bucket")

    credentials_encrypted = encrypt_credentials(creds)

    # Upsert: update if exists, create if not
    result = await db.execute(
        select(StorageConnection).where(StorageConnection.event_id == event_id)
    )
    conn = result.scalar_one_or_none()

    if conn:
        conn.storage_type = body.storage_type
        conn.credentials_encrypted = credentials_encrypted
        conn.bucket_name = bucket_name
        conn.bucket_region = bucket_region
        conn.dropbox_folder_path = folder_path
        conn.is_verified = False
    else:
        conn = StorageConnection(
            event_id=event_id,
            storage_type=body.storage_type,
            credentials_encrypted=credentials_encrypted,
            bucket_name=bucket_name,
            bucket_region=bucket_region,
            dropbox_folder_path=folder_path,
        )
        db.add(conn)

    await db.flush()
    return StorageResponse.model_validate(conn)


@router.post("/{event_id}/storage/verify", response_model=dict)
async def verify_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Test storage connection by verifying credentials."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(StorageConnection).where(StorageConnection.event_id == event_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise NotFoundError("storage configuration")

    from app.services.storage_backends import get_storage_backend
    backend = get_storage_backend(conn)
    ok = await backend.verify_connection()

    conn.is_verified = ok
    await db.flush()

    if not ok:
        raise AppError(400, "STORAGE_VERIFY_FAILED", "Could not connect to storage backend — check your credentials")

    return {"verified": True}


@router.post("/{event_id}/storage/managed", response_model=StorageResponse, status_code=201)
async def provision_managed_s3(
    event_id: UUID,
    body: ManagedS3Request,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Provision an EventVault-managed S3 bucket for this event."""
    from app.config import get_settings
    settings = get_settings()

    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise AppError(503, "MANAGED_S3_UNAVAILABLE", "Managed S3 is not configured on this server")

    await _get_event_or_403(event_id, user_id, db)

    # Prevent double-provisioning
    result = await db.execute(
        select(StorageConnection).where(StorageConnection.event_id == event_id)
    )
    if result.scalar_one_or_none():
        raise AppError(409, "STORAGE_EXISTS", "Storage is already configured for this event")

    from app.services.storage_backends import ManagedS3Backend
    try:
        backend = ManagedS3Backend.provision_bucket(str(event_id), region=body.region)
    except Exception as exc:
        raise AppError(500, "BUCKET_PROVISION_FAILED", f"Failed to provision S3 bucket: {exc}")

    # Managed S3 uses platform credentials, so we store a minimal marker
    creds_encrypted = encrypt_credentials(json.dumps({"managed": True}))
    conn = StorageConnection(
        event_id=event_id,
        storage_type=StorageType.MANAGED_S3,
        credentials_encrypted=creds_encrypted,
        bucket_name=backend.bucket_name,
        bucket_region=backend.region,
        is_verified=True,
    )
    db.add(conn)
    await db.flush()
    return StorageResponse.model_validate(conn)


@router.delete("/{event_id}/storage", status_code=204)
async def remove_storage(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove storage configuration."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(StorageConnection).where(StorageConnection.event_id == event_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise NotFoundError("storage configuration")

    await db.delete(conn)
    await db.flush()
