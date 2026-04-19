"""
EventVault Configuration
Pydantic Settings for environment-based configuration
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "EventVault"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/eventvault"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-64"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Encryption (for storage credentials)
    ENCRYPTION_KEY: str = "CHANGE-ME-generate-with-cryptography-fernet-generate-key"

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # AWS (for managed S3 provisioning)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"

    # Dropbox OAuth
    DROPBOX_APP_KEY: Optional[str] = None
    DROPBOX_APP_SECRET: Optional[str] = None

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 500
    UPLOAD_TEMP_DIR: str = "/tmp/eventvault/uploads"
    CHUNK_SIZE_MB: int = 5

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "https://app.eventvault.io",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
