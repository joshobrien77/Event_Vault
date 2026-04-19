"""Event link and QR code routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

router = APIRouter()


@router.get("/{event_id}/links")
async def list_links(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all links for an event."""
    # TODO: Implement
    return {"data": []}


@router.post("/{event_id}/links")
async def create_link(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new short link + QR code for an event."""
    # TODO: Implement — generate short_code, create QR with qrcode lib
    return {"message": "create link endpoint"}


@router.delete("/{event_id}/links/{link_id}")
async def deactivate_link(
    event_id: UUID,
    link_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a link."""
    # TODO: Implement
    return {"message": "deactivate link endpoint"}


@router.get("/{event_id}/links/{link_id}/qr")
async def download_qr(
    event_id: UUID,
    link_id: UUID,
    format: str = "png",
    size: int = 512,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Download QR code image in PNG or SVG format."""
    # TODO: Implement — return FileResponse
    return {"message": "qr download endpoint"}
