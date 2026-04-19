"""Event CRUD routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

router = APIRouter()


@router.get("/")
async def list_events(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all events for the authenticated host."""
    # TODO: Implement
    return {"data": [], "meta": {"page": 1, "total": 0}}


@router.post("/")
async def create_event(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new event."""
    # TODO: Implement
    return {"message": "create event endpoint"}


@router.get("/{event_id}")
async def get_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get event details."""
    # TODO: Implement
    return {"message": "get event endpoint"}


@router.patch("/{event_id}")
async def update_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update event settings."""
    # TODO: Implement
    return {"message": "update event endpoint"}


@router.delete("/{event_id}")
async def delete_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete an event."""
    # TODO: Implement
    return {"message": "delete event endpoint"}


@router.post("/{event_id}/archive")
async def archive_event(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Archive an event."""
    # TODO: Implement
    return {"message": "archive event endpoint"}
