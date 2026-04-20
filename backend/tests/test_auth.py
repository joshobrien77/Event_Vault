"""Auth endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "strongpass1",
        "name": "New User",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession):
    await make_user(db, email="dup@example.com")
    resp = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "strongpass1",
        "name": "Dup User",
    })
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weak@example.com",
        "password": "short",
        "name": "User",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db: AsyncSession):
    await make_user(db, email="login@example.com", password="mypassword")
    resp = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "mypassword",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db: AsyncSession):
    await make_user(db, email="badpass@example.com", password="correct")
    resp = await client.post("/api/v1/auth/login", json={
        "email": "badpass@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, db: AsyncSession):
    await make_user(db, email="refresh@example.com")
    login = await client.post("/api/v1/auth/login", json={
        "email": "refresh@example.com",
        "password": "password123",
    })
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(client: AsyncClient, db: AsyncSession):
    await make_user(db, email="badrefresh@example.com")
    login = await client.post("/api/v1/auth/login", json={
        "email": "badrefresh@example.com",
        "password": "password123",
    })
    access_token = login.json()["access_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401
