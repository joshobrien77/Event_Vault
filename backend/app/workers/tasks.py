"""
Celery tasks for asynchronous upload processing.
"""

from celery import Celery
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
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_upload(self, upload_id: str):
    """
    Process an uploaded file:
    1. Extract EXIF metadata (images) or duration (video)
    2. Generate thumbnail
    3. Push to configured storage backend
    4. Update Upload record with final path and status
    5. Clean up temp file
    """
    # TODO: Implement
    # This runs synchronously inside Celery worker.
    # Use synchronous DB session and storage calls here.
    pass


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_thumbnail(self, upload_id: str):
    """
    Generate thumbnail for an upload.
    - Images: Pillow resize to 400x400 max
    - Videos: ffmpeg extract frame at 1s, resize
    """
    # TODO: Implement
    pass


@celery_app.task
def cleanup_expired_events():
    """
    Periodic task: archive events past their expiration date.
    Run via Celery Beat schedule.
    """
    # TODO: Implement
    pass
