"""
EventVault Database Models
SQLAlchemy 2.0 async ORM models with PostgreSQL
"""

import uuid
from datetime import datetime, date
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String, Text, Integer, BigInteger, Boolean, Float,
    DateTime, Date, ForeignKey, Index, Enum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


# --- Base ---

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --- Enums ---

class EventType(str, PyEnum):
    WEDDING = "wedding"
    GRADUATION = "graduation"
    BIRTHDAY = "birthday"
    CORPORATE = "corporate"
    OTHER = "other"


class EventStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class EventTierName(str, PyEnum):
    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"


class StorageType(str, PyEnum):
    DROPBOX = "dropbox"
    S3 = "s3"
    MANAGED_S3 = "managed_s3"


class UploadStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


# --- Models ---

class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    events: Mapped[List["Event"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="user")


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type_enum"), nullable=False, default=EventType.OTHER
    )
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status_enum"), nullable=False, default=EventStatus.DRAFT
    )
    tier: Mapped[EventTierName] = mapped_column(
        Enum(EventTierName, name="event_tier_enum"), nullable=False, default=EventTierName.FREE
    )
    upload_limit_mb: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    total_storage_limit_gb: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    guest_pin: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)
    allow_video: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_photo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    welcome_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="events")
    links: Mapped[List["EventLink"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    storage_connection: Mapped[Optional["StorageConnection"]] = relationship(
        back_populates="event", uselist=False, cascade="all, delete-orphan"
    )
    uploads: Mapped[List["Upload"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="event")

    __table_args__ = (
        Index("ix_events_user_status", "user_id", "status"),
    )


class EventLink(TimestampMixin, Base):
    __tablename__ = "event_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    short_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    qr_code_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="links")


class StorageConnection(TimestampMixin, Base):
    __tablename__ = "storage_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    storage_type: Mapped[StorageType] = mapped_column(
        Enum(StorageType, name="storage_type_enum"), nullable=False
    )
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    bucket_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bucket_region: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    dropbox_folder_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="storage_connection")


class Upload(TimestampMixin, Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    guest_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    guest_device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status_enum"), nullable=False, default=UploadStatus.PENDING
    )
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exif_taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="uploads")

    __table_args__ = (
        Index("ix_uploads_event_status", "event_id", "status"),
        Index("ix_uploads_event_created", "event_id", "created_at"),
    )


class EventTier(TimestampMixin, Base):
    __tablename__ = "event_tiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[EventTierName] = mapped_column(
        Enum(EventTierName, name="event_tier_name_enum"), unique=True, nullable=False
    )
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uploads: Mapped[int] = mapped_column(Integer, nullable=False)  # -1 = unlimited
    max_file_size_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    max_total_storage_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    allows_video: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allows_custom_branding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    managed_s3_monthly_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), index=True, nullable=True
    )
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum"), nullable=False, default=PaymentStatus.PENDING
    )
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="payments")
    event: Mapped[Optional["Event"]] = relationship(back_populates="payments")
