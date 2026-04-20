"""Event CRUD routes."""

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import get_current_user_id
from app.models.models import Event, EventStatus
from app.schemas.schemas import EventCreate, EventResponse, EventUpdate

router = APIRouter()


async def _get_event_for_user(event_id: UUID, user_id: UUID, db: AsyncSession) -> Event:
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.deleted_at.is_(None))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise NotFoundError("event")
    if event.user_id != user_id:
        raise ForbiddenError()
    return event


@router.get("/", response_model=dict)
async def list_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str = Query(None),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all events for the authenticated host."""
    q = select(Event).where(Event.user_id == user_id, Event.deleted_at.is_(None))

    if status:
        try:
            q = q.where(Event.status == EventStatus(status))
        except ValueError:
            pass

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.order_by(Event.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    events = result.scalars().all()

    return {
        "data": [EventResponse.model_validate(e) for e in events],
        "meta": {"page": page, "per_page": per_page, "total": total},
    }


@router.post("/", response_model=EventResponse, status_code=201)
async def create_event(
    body: EventCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new event."""
    event = Event(
        user_id=user_id,
        name=body.name,
        event_type=body.event_type,
        event_date=body.event_date,
        guest_pin=body.guest_pin,
        allow_video=body.allow_video,
        allow_photo=body.allow_photo,
        welcome_message=body.welcome_message,
        status=EventStatus.DRAFT,
    )
    db.add(event)
    await db.flush()
    return EventResponse.model_validate(event)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get event details."""
    event = await _get_event_for_user(event_id, user_id, db)
    return EventResponse.model_validate(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    body: EventUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update event settings."""
    event = await _get_event_for_user(event_id, user_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    await db.flush()
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete an event."""
    event = await _get_event_for_user(event_id, user_id, db)
    event.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/{event_id}/archive", response_model=EventResponse)
async def archive_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Archive an event."""
    event = await _get_event_for_user(event_id, user_id, db)
    event.status = EventStatus.ARCHIVED
    await db.flush()
    return EventResponse.model_validate(event)
