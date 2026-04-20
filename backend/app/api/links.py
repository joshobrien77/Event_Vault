"""Event link and QR code routes."""

import secrets
from io import BytesIO
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import get_current_user_id
from app.models.models import Event, EventLink
from app.schemas.schemas import LinkCreate, LinkResponse

router = APIRouter()

settings = get_settings()


def _generate_short_code(length: int = 8) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _make_qr_png(url: str, size: int) -> BytesIO:
    qr = qrcode.QRCode(box_size=max(1, size // 37), border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


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


@router.get("/{event_id}/links", response_model=dict)
async def list_links(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all links for an event."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(EventLink)
        .where(EventLink.event_id == event_id)
        .order_by(EventLink.created_at.desc())
    )
    links = result.scalars().all()

    base = f"{settings.BASE_URL}/e"
    data = []
    for link in links:
        resp = LinkResponse.model_validate(link)
        resp.full_url = f"{base}/{link.short_code}"
        data.append(resp)

    return {"data": data}


@router.post("/{event_id}/links", response_model=LinkResponse, status_code=201)
async def create_link(
    event_id: UUID,
    body: LinkCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new short link + QR code for an event."""
    await _get_event_or_403(event_id, user_id, db)

    # Generate a unique short code
    for _ in range(10):
        code = _generate_short_code()
        existing = await db.execute(select(EventLink).where(EventLink.short_code == code))
        if not existing.scalar_one_or_none():
            break

    link = EventLink(
        event_id=event_id,
        short_code=code,
        label=body.label,
        expires_at=body.expires_at,
    )
    db.add(link)
    await db.flush()

    resp = LinkResponse.model_validate(link)
    resp.full_url = f"{settings.BASE_URL}/e/{code}"
    return resp


@router.delete("/{event_id}/links/{link_id}", status_code=204)
async def deactivate_link(
    event_id: UUID,
    link_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a link."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(EventLink).where(EventLink.id == link_id, EventLink.event_id == event_id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("link")

    link.is_active = False
    await db.flush()


@router.get("/{event_id}/links/{link_id}/qr")
async def download_qr(
    event_id: UUID,
    link_id: UUID,
    format: str = Query("png", pattern="^(png|svg)$"),
    size: int = Query(512, ge=128, le=2048),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Download QR code image in PNG or SVG format."""
    await _get_event_or_403(event_id, user_id, db)

    result = await db.execute(
        select(EventLink).where(EventLink.id == link_id, EventLink.event_id == event_id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("link")

    url = f"{settings.BASE_URL}/e/{link.short_code}"

    if format == "svg":
        import qrcode.image.svg as qr_svg
        factory = qr_svg.SvgImage
        img = qrcode.make(url, image_factory=factory)
        buf = BytesIO()
        img.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="qr-{link.short_code}.svg"'},
        )

    buf = _make_qr_png(url, size)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="qr-{link.short_code}.png"'},
    )
