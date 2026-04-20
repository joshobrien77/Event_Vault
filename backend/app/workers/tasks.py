"""Celery tasks for asynchronous upload processing."""

import asyncio
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery
from PIL import Image

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "eventvault",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "cleanup-expired-events": {
            "task": "app.workers.tasks.cleanup_expired_events",
            "schedule": 3600.0,  # every hour
        }
    },
)


async def _do_process_upload(upload_id: str) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload

    from app.models.models import Event, Upload, UploadStatus
    from app.services.storage_backends import get_storage_backend

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            result = await db.execute(
                select(Upload)
                .options(selectinload(Upload.event).selectinload(Event.storage_connection))
                .where(Upload.id == uuid.UUID(upload_id))
            )
            upload = result.scalar_one_or_none()
            if not upload:
                return

            upload.status = UploadStatus.PROCESSING
            await db.commit()

            temp_path = Path(settings.UPLOAD_TEMP_DIR) / upload_id
            if not temp_path.exists():
                raise FileNotFoundError(f"Temp file not found: {temp_path}")

            width = height = None
            exif_taken_at = None
            duration_seconds = None
            thumb_path = None

            if upload.mime_type.startswith("image/"):
                try:
                    with Image.open(temp_path) as img:
                        width, height = img.size
                        # Extract DateTimeOriginal (EXIF tag 36867)
                        exif_raw = img._getexif()
                        if exif_raw and 36867 in exif_raw:
                            try:
                                exif_taken_at = datetime.strptime(
                                    exif_raw[36867], "%Y:%m:%d %H:%M:%S"
                                ).replace(tzinfo=timezone.utc)
                            except ValueError:
                                pass

                        # Thumbnail
                        thumb_path = Path(settings.UPLOAD_TEMP_DIR) / f"{upload_id}_thumb.jpg"
                        thumb = img.copy()
                        thumb.thumbnail((400, 400), Image.LANCZOS)
                        if thumb.mode in ("RGBA", "P", "LA"):
                            thumb = thumb.convert("RGB")
                        thumb.save(thumb_path, "JPEG", quality=85, optimize=True)
                except Exception:
                    pass  # Don't fail upload for thumbnail errors

            elif upload.mime_type.startswith("video/"):
                # Get dimensions + duration via ffprobe
                try:
                    probe = subprocess.run(
                        [
                            "ffprobe", "-v", "quiet",
                            "-print_format", "json",
                            "-show_streams",
                            str(temp_path),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if probe.returncode == 0:
                        data = json.loads(probe.stdout)
                        for stream in data.get("streams", []):
                            if stream.get("codec_type") == "video":
                                width = stream.get("width")
                                height = stream.get("height")
                                duration_seconds = float(stream.get("duration", 0) or 0)
                                break
                except Exception:
                    pass

                # Video thumbnail at 1 second
                try:
                    thumb_path = Path(settings.UPLOAD_TEMP_DIR) / f"{upload_id}_thumb.jpg"
                    subprocess.run(
                        [
                            "ffmpeg", "-y",
                            "-ss", "1",
                            "-i", str(temp_path),
                            "-vframes", "1",
                            "-vf", "scale=400:-1",
                            str(thumb_path),
                        ],
                        capture_output=True,
                        timeout=30,
                    )
                    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
                        thumb_path = None
                except Exception:
                    thumb_path = None

            # Push to storage backend
            storage_path = None
            thumbnail_storage_path = None

            if upload.event and upload.event.storage_connection:
                backend = get_storage_backend(upload.event.storage_connection)
                remote_base = f"{upload.event_id}/{upload_id}"
                storage_path = await backend.upload_file(
                    temp_path, f"{remote_base}/{upload.original_filename}"
                )
                if thumb_path and thumb_path.exists():
                    thumbnail_storage_path = await backend.upload_file(
                        thumb_path, f"{remote_base}/thumb.jpg"
                    )

            # Update record
            upload.status = UploadStatus.COMPLETED
            upload.storage_path = storage_path
            upload.thumbnail_path = thumbnail_storage_path
            upload.width = width
            upload.height = height
            upload.duration_seconds = duration_seconds
            upload.exif_taken_at = exif_taken_at
            await db.commit()

        except Exception as exc:
            try:
                result = await db.execute(
                    select(Upload).where(Upload.id == uuid.UUID(upload_id))
                )
                upload = result.scalar_one_or_none()
                if upload:
                    upload.status = UploadStatus.FAILED
                    upload.error_message = str(exc)[:500]
                    await db.commit()
            except Exception:
                pass
            raise

        finally:
            # Clean up temp files regardless of outcome
            temp_path = Path(settings.UPLOAD_TEMP_DIR) / upload_id
            temp_path.unlink(missing_ok=True)
            thumb = Path(settings.UPLOAD_TEMP_DIR) / f"{upload_id}_thumb.jpg"
            thumb.unlink(missing_ok=True)

    await engine.dispose()


async def _mark_upload_failed(upload_id: str, error: str) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models.models import Upload, UploadStatus

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(select(Upload).where(Upload.id == uuid.UUID(upload_id)))
        upload = result.scalar_one_or_none()
        if upload:
            upload.status = UploadStatus.FAILED
            upload.error_message = error[:500]
            await db.commit()
    await engine.dispose()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_upload(self, upload_id: str):
    """Process an uploaded file: metadata, thumbnail, push to storage."""
    try:
        asyncio.run(_do_process_upload(upload_id))
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            asyncio.run(_mark_upload_failed(upload_id, str(exc)))


async def _cleanup_expired_async() -> None:
    from datetime import datetime, timezone

    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models.models import Event, EventStatus

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Event).where(
                Event.expires_at < now,
                Event.status == EventStatus.ACTIVE,
                Event.deleted_at.is_(None),
            )
        )
        events = result.scalars().all()
        for event in events:
            event.status = EventStatus.ARCHIVED
        if events:
            await db.commit()
    await engine.dispose()


@celery_app.task
def cleanup_expired_events():
    """Periodic task: archive events past their expiration date."""
    asyncio.run(_cleanup_expired_async())
