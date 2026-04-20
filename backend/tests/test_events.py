"""Event CRUD endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_headers, make_event, make_user


@pytest.mark.asyncio
async def test_create_event(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    resp = await client.post(
        "/api/v1/events/",
        json={"name": "My Wedding", "event_type": "wedding"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Wedding"
    assert data["event_type"] == "wedding"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_create_event_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/v1/events/", json={"name": "X"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_events(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    await make_event(db, user, name="Event A")
    await make_event(db, user, name="Event B")

    resp = await client.get("/api/v1/events/", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] >= 2
    names = [e["name"] for e in body["data"]]
    assert "Event A" in names
    assert "Event B" in names


@pytest.mark.asyncio
async def test_list_events_isolated_per_user(client: AsyncClient, db: AsyncSession):
    user_a = await make_user(db)
    user_b = await make_user(db)
    await make_event(db, user_a, name="A's Event")
    await make_event(db, user_b, name="B's Event")

    resp = await client.get("/api/v1/events/", headers=auth_headers(user_a))
    names = [e["name"] for e in resp.json()["data"]]
    assert "A's Event" in names
    assert "B's Event" not in names


@pytest.mark.asyncio
async def test_get_event(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user, name="Get Me")

    resp = await client.get(f"/api/v1/events/{event.id}", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_event_not_found(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    import uuid
    resp = await client.get(f"/api/v1/events/{uuid.uuid4()}", headers=auth_headers(user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_event_wrong_user(client: AsyncClient, db: AsyncSession):
    owner = await make_user(db)
    other = await make_user(db)
    event = await make_event(db, owner)

    resp = await client.get(f"/api/v1/events/{event.id}", headers=auth_headers(other))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_event(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user, name="Old Name")

    resp = await client.patch(
        f"/api/v1/events/{event.id}",
        json={"name": "New Name", "welcome_message": "Welcome!"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["welcome_message"] == "Welcome!"


@pytest.mark.asyncio
async def test_delete_event_soft(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.delete(f"/api/v1/events/{event.id}", headers=auth_headers(user))
    assert resp.status_code == 204

    # Deleted event should not appear in list
    list_resp = await client.get("/api/v1/events/", headers=auth_headers(user))
    ids = [e["id"] for e in list_resp.json()["data"]]
    assert str(event.id) not in ids


@pytest.mark.asyncio
async def test_archive_event(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    event = await make_event(db, user)

    resp = await client.post(f"/api/v1/events/{event.id}/archive", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_create_event_with_pin(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    resp = await client.post(
        "/api/v1/events/",
        json={"name": "Private", "guest_pin": "1234"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_event_invalid_pin(client: AsyncClient, db: AsyncSession):
    user = await make_user(db)
    resp = await client.post(
        "/api/v1/events/",
        json={"name": "Bad PIN", "guest_pin": "abc"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 422
