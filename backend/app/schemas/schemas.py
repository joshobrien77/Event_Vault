"""
Pydantic v2 schemas for API request/response validation.
"""

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.models import EventType, EventStatus, EventTierName, StorageType, UploadStatus


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# --- Events ---

class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    event_type: EventType = EventType.OTHER
    event_date: Optional[date] = None
    guest_pin: Optional[str] = Field(default=None, min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    allow_video: bool = True
    allow_photo: bool = True
    welcome_message: Optional[str] = None


class EventUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    event_type: Optional[EventType] = None
    event_date: Optional[date] = None
    guest_pin: Optional[str] = Field(default=None, pattern=r"^\d{4,6}$")
    allow_video: Optional[bool] = None
    allow_photo: Optional[bool] = None
    welcome_message: Optional[str] = None
    expires_at: Optional[datetime] = None


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    event_type: EventType
    event_date: Optional[date]
    status: EventStatus
    tier: EventTierName
    upload_limit_mb: int
    total_storage_limit_gb: int
    allow_video: bool
    allow_photo: bool
    welcome_message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# --- Event Links ---

class LinkCreate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    short_code: str
    full_url: str = ""
    qr_code_path: Optional[str]
    label: Optional[str]
    is_active: bool
    click_count: int
    expires_at: Optional[datetime]
    created_at: datetime


# --- Storage ---

class StorageSetup(BaseModel):
    storage_type: StorageType

    # S3 fields
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    bucket_name: Optional[str] = None
    bucket_region: Optional[str] = "us-east-1"

    # Dropbox fields
    dropbox_access_token: Optional[str] = None
    dropbox_refresh_token: Optional[str] = None
    dropbox_folder_path: Optional[str] = "/EventVault"


class ManagedS3Request(BaseModel):
    region: str = "us-east-1"


class StorageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    storage_type: StorageType
    bucket_name: Optional[str]
    bucket_region: Optional[str]
    dropbox_folder_path: Optional[str]
    is_verified: bool
    created_at: datetime


# --- Uploads ---

class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guest_name: Optional[str]
    original_filename: str
    file_size_bytes: int
    mime_type: str
    status: UploadStatus
    thumbnail_path: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration_seconds: Optional[float]
    exif_taken_at: Optional[datetime]
    created_at: datetime


class UploadStatsResponse(BaseModel):
    total_uploads: int
    completed_uploads: int
    failed_uploads: int
    pending_uploads: int
    total_size_bytes: int
    photo_count: int
    video_count: int


# --- Guest ---

class GuestEventInfo(BaseModel):
    """What guests see when they open an event link."""
    event_name: str
    event_type: EventType
    welcome_message: Optional[str]
    allow_photo: bool
    allow_video: bool
    upload_limit_mb: int
    requires_pin: bool


class PinVerifyRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=6)


# --- Billing ---

class TierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: EventTierName
    price_cents: int
    max_uploads: int
    max_file_size_mb: int
    max_total_storage_gb: int
    allows_video: bool
    allows_custom_branding: bool
    managed_s3_monthly_cents: int


class CheckoutRequest(BaseModel):
    event_id: UUID
    tier: EventTierName


# --- Chunked upload ---

class ChunkedUploadInit(BaseModel):
    filename: str
    mime_type: str
    file_size_bytes: int
    total_chunks: int
    guest_name: Optional[str] = None
    pin: Optional[str] = None


# --- Generic ---

class PaginatedResponse(BaseModel):
    data: list
    meta: dict = {"page": 1, "per_page": 50, "total": 0}
