"""
Shared test fixtures.

Requires a PostgreSQL test database. Set TEST_DATABASE_URL env var or use the default:
  postgresql+asyncpg://postgres:postgres@localhost:5432/eventvault_test

Run migrations before tests:
  DATABASE_URL=$TEST_DATABASE_URL alembic upgrade head
"""

import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.models import Base, Event, EventLink, EventStatus, EventType, Upload, UploadStatus, User

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/eventvault_test",
)

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed event tiers (mirrors the Alembic migration seed data)
    async with TestSessionFactory() as session:
        from sqlalchemy import select
        from app.models.models import EventTier, EventTierName
        existing = await session.execute(select(EventTier))
        if not existing.scalars().first():
            for tier_data in [
                dict(name=EventTierName.FREE, price_cents=0, max_uploads=50, max_file_size_mb=10,
                     max_total_storage_gb=1, allows_video=False, allows_custom_branding=False),
                dict(name=EventTierName.STANDARD, price_cents=1500, max_uploads=500, max_file_size_mb=50,
                     max_total_storage_gb=10, allows_video=True, allows_custom_branding=False),
                dict(name=EventTierName.PREMIUM, price_cents=4900, max_uploads=-1, max_file_size_mb=500,
                     max_total_storage_gb=100, allows_video=True, allows_custom_branding=True),
            ]:
                session.add(EventTier(**tier_data))
            await session.commit()

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Model factories ---

async def make_user(db: AsyncSession, email: str = None, password: str = "password123") -> User:
    user = User(
        email=email or f"user_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(password),
        name="Test User",
    )
    db.add(user)
    await db.flush()
    return user


async def make_event(db: AsyncSession, user: User, **kwargs) -> Event:
    event = Event(
        user_id=user.id,
        name=kwargs.get("name", "Test Event"),
        event_type=kwargs.get("event_type", EventType.OTHER),
        status=kwargs.get("status", EventStatus.ACTIVE),
        allow_video=kwargs.get("allow_video", True),
        allow_photo=kwargs.get("allow_photo", True),
        upload_limit_mb=kwargs.get("upload_limit_mb", 25),
    )
    db.add(event)
    await db.flush()
    return event


async def make_link(db: AsyncSession, event: Event, short_code: str = None) -> EventLink:
    link = EventLink(
        event_id=event.id,
        short_code=short_code or uuid.uuid4().hex[:8],
        is_active=True,
    )
    db.add(link)
    await db.flush()
    return link


def auth_headers(user: User) -> dict:
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}
