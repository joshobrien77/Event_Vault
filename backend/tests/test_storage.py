"""Storage endpoint tests."""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_credentials
from app.models.models import StorageConnection, StorageType
from tests.conftest import auth_headers, make_event, make_user


async def make_storage(db: AsyncSession, event, storage_type=StorageType.S3) -> StorageConnection:
    creds = encrypt_credentials(json.dumps({"aws_access_key_id": "FAKE", "aws_secret_access_key": "FAKE"}))
    conn = StorageConnection(
        event_id=event.id,
        storage_type=storage_type,
        credentials_encrypted=creds,
        bucket_name="test-bucket",
        bucket_region="us-east-1",
        is_verified=False,
    )
    db.add(conn)
    await db.flush()
    return conn


@pytest.mark.asyncio
async def test_set_storage_s3(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.put(
        f"/api/v1/events/{event.id}/storage",
        json={
            "storage_type": "s3",
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "bucket_name": "my-event-bucket",
            "bucket_region": "us-west-2",
        },
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["storage_type"] == "s3"
    assert data["bucket_name"] == "my-event-bucket"
    assert data["is_verified"] is False
    # Credentials must NOT appear in response
    assert "aws_access_key_id" not in data
    assert "credentials_encrypted" not in data


@pytest.mark.asyncio
async def test_set_storage_dropbox(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.put(
        f"/api/v1/events/{event.id}/storage",
        json={
            "storage_type": "dropbox",
            "dropbox_access_token": "sl.fake_token_abc123",
            "dropbox_folder_path": "/MyEvents",
        },
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["storage_type"] == "dropbox"
    assert data["dropbox_folder_path"] == "/MyEvents"


@pytest.mark.asyncio
async def test_set_storage_missing_s3_fields(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.put(
        f"/api/v1/events/{event.id}/storage",
        json={"storage_type": "s3"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_storage(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    await make_storage(db, event)

    resp = await client.get(f"/api/v1/events/{event.id}/storage", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["storage_type"] == "s3"


@pytest.mark.asyncio
async def test_get_storage_not_configured(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.get(f"/api/v1/events/{event.id}/storage", headers=auth_headers(user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_storage(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)
    await make_storage(db, event)

    resp = await client.delete(f"/api/v1/events/{event.id}/storage", headers=auth_headers(user))
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/events/{event.id}/storage", headers=auth_headers(user))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_storage_wrong_user(client: AsyncClient, db: AsyncSession):
    owner = await make_user(db)
    other = await make_user(db)
    event = await make_event(db, owner)

    resp = await client.get(f"/api/v1/events/{event.id}/storage", headers=auth_headers(other))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_storage_replaces_existing(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    # Set initial
    await client.put(
        f"/api/v1/events/{event.id}/storage",
        json={
            "storage_type": "s3",
            "aws_access_key_id": "KEY1",
            "aws_secret_access_key": "SECRET1",
            "bucket_name": "bucket-one",
        },
        headers=auth_headers(user),
    )

    # Update
    resp = await client.put(
        f"/api/v1/events/{event.id}/storage",
        json={
            "storage_type": "s3",
            "aws_access_key_id": "KEY2",
            "aws_secret_access_key": "SECRET2",
            "bucket_name": "bucket-two",
        },
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["bucket_name"] == "bucket-two"


@pytest.mark.asyncio
async def test_billing_tiers(client: AsyncClient):
    """Tiers are seeded in migration — should return 3."""
    resp = await client.get("/api/v1/billing/tiers")
    assert resp.status_code == 200
    tiers = resp.json()["data"]
    names = [t["name"] for t in tiers]
    assert "free" in names
    assert "standard" in names
    assert "premium" in names
