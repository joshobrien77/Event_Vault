"""Upload and guest endpoint tests."""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Upload, UploadStatus
from tests.conftest import auth_headers, make_event, make_link, make_user


async def make_upload(db: AsyncSession, event, **kwargs) -> Upload:
    upload = Upload(
        event_id=event.id,
        original_filename=kwargs.get("original_filename", "photo.jpg"),
        file_size_bytes=kwargs.get("file_size_bytes", 1024),
        mime_type=kwargs.get("mime_type", "image/jpeg"),
        status=kwargs.get("status", UploadStatus.COMPLETED),
    )
    db.add(upload)
    await db.flush()
    return upload


# --- Guest: resolve link ---

@pytest.mark.asyncio
async def test_resolve_link(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user, name="My Party")
    link = await make_link(db, event)

    resp = await client.get(f"/api/v1/e/{link.short_code}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_name"] == "My Party"
    assert data["requires_pin"] is False


@pytest.mark.asyncio
async def test_resolve_link_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/e/doesnotexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_link_with_pin(client: AsyncClient, db: AsyncSession):
    from app.models.models import EventStatus
    user = await make_user(db)
    event = await make_event(db, user)
    event.guest_pin = "1234"
    await db.flush()
    link = await make_link(db, event)

    resp = await client.get(f"/api/v1/e/{link.short_code}")
    assert resp.status_code == 200
    assert resp.json()["requires_pin"] is True


# --- Guest: verify PIN ---

@pytest.mark.asyncio
async def test_verify_pin_correct(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    event.guest_pin = "5678"
    await db.flush()
    link = await make_link(db, event)

    resp = await client.post(f"/api/v1/e/{link.short_code}/verify-pin", json={"pin": "5678"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_verify_pin_wrong(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    event.guest_pin = "5678"
    await db.flush()
    link = await make_link(db, event)

    resp = await client.post(f"/api/v1/e/{link.short_code}/verify-pin", json={"pin": "0000"})
    assert resp.status_code == 401


# --- Host: list uploads ---

@pytest.mark.asyncio
async def test_list_uploads(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    await make_upload(db, event)
    await make_upload(db, event)

    resp = await client.get(f"/api/v1/events/{event.id}/uploads", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] >= 2


@pytest.mark.asyncio
async def test_list_uploads_wrong_user(client: AsyncClient, db: AsyncSession):
    owner = await make_user(db)
    other = await make_user(db)
    event = await make_event(db, owner)

    resp = await client.get(f"/api/v1/events/{event.id}/uploads", headers=auth_headers(other))
    assert resp.status_code == 403


# --- Host: upload stats ---

@pytest.mark.asyncio
async def test_upload_stats(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    await make_upload(db, event, mime_type="image/jpeg", file_size_bytes=500_000, status=UploadStatus.COMPLETED)
    await make_upload(db, event, mime_type="video/mp4", file_size_bytes=10_000_000, status=UploadStatus.FAILED)

    resp = await client.get(f"/api/v1/events/{event.id}/uploads/stats", headers=auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_uploads"] == 2
    assert data["photo_count"] == 1
    assert data["video_count"] == 1
    assert data["completed_uploads"] == 1
    assert data["failed_uploads"] == 1


# --- Host: get single upload ---

@pytest.mark.asyncio
async def test_get_upload(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    upload = await make_upload(db, event)

    resp = await client.get(f"/api/v1/events/{event.id}/uploads/{upload.id}", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(upload.id)


@pytest.mark.asyncio
async def test_get_upload_not_found(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.get(
        f"/api/v1/events/{event.id}/uploads/{uuid.uuid4()}",
        headers=auth_headers(user),
    )
    assert resp.status_code == 404


# --- Host: delete upload ---

@pytest.mark.asyncio
async def test_delete_upload(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    upload = await make_upload(db, event)

    resp = await client.delete(
        f"/api/v1/events/{event.id}/uploads/{upload.id}",
        headers=auth_headers(user),
    )
    assert resp.status_code == 204

    # Verify gone
    get_resp = await client.get(
        f"/api/v1/events/{event.id}/uploads/{upload.id}",
        headers=auth_headers(user),
    )
    assert get_resp.status_code == 404
