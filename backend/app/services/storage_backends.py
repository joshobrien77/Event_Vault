"""
Storage backend abstraction layer.
Provides a unified interface for uploading files to Dropbox, S3, or Managed S3.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from app.core.security import decrypt_credentials


class StorageBackend(ABC):
    """Abstract base class for all storage backends."""

    @abstractmethod
    async def upload_file(self, local_path: Path, remote_path: str) -> str:
        """Upload a file and return the final remote path."""
        ...

    @abstractmethod
    async def delete_file(self, remote_path: str) -> bool:
        """Delete a file from storage. Returns True on success."""
        ...

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Test that the storage connection is valid."""
        ...

    @abstractmethod
    async def get_download_url(self, remote_path: str, expires: int = 3600) -> str:
        """Generate a temporary download URL."""
        ...


class S3Backend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(self, credentials_encrypted: str, bucket_name: str, region: str):
        creds = json.loads(decrypt_credentials(credentials_encrypted))
        self.bucket_name = bucket_name
        self.region = region
        self.client = boto3.client(
            "s3",
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    async def upload_file(self, local_path: Path, remote_path: str) -> str:
        self.client.upload_file(str(local_path), self.bucket_name, remote_path)
        return remote_path

    async def delete_file(self, remote_path: str) -> bool:
        self.client.delete_object(Bucket=self.bucket_name, Key=remote_path)
        return True

    async def verify_connection(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception:
            return False

    async def get_download_url(self, remote_path: str, expires: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": remote_path},
            ExpiresIn=expires,
        )


class ManagedS3Backend(S3Backend):
    """
    EventVault-managed S3 bucket.
    Same as S3Backend but uses EventVault's own AWS credentials
    and provisions buckets automatically.
    """

    def __init__(self, bucket_name: str, region: str):
        from app.config import get_settings
        settings = get_settings()
        self.bucket_name = bucket_name
        self.region = region
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    @classmethod
    def provision_bucket(cls, event_id: str, region: str = "us-east-1") -> "ManagedS3Backend":
        """Create a new S3 bucket for an event."""
        from app.config import get_settings
        settings = get_settings()

        bucket_name = f"eventvault-managed-{event_id}"
        client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=region,
        )

        create_kwargs = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": region
            }
        client.create_bucket(**create_kwargs)

        # Set CORS for web uploads
        client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": ["*"],
                        "AllowedMethods": ["GET", "PUT"],
                        "AllowedHeaders": ["*"],
                        "MaxAgeSeconds": 3600,
                    }
                ]
            },
        )

        return cls(bucket_name=bucket_name, region=region)


class DropboxBackend(StorageBackend):
    """Dropbox storage backend."""

    def __init__(self, credentials_encrypted: str, folder_path: str):
        creds = json.loads(decrypt_credentials(credentials_encrypted))
        self.access_token = creds["access_token"]
        self.refresh_token = creds.get("refresh_token")
        self.folder_path = folder_path.rstrip("/")

    async def upload_file(self, local_path: Path, remote_path: str) -> str:
        import dropbox
        dbx = dropbox.Dropbox(self.access_token)
        full_path = f"{self.folder_path}/{remote_path}"
        with open(local_path, "rb") as f:
            dbx.files_upload(f.read(), full_path)
        return full_path

    async def delete_file(self, remote_path: str) -> bool:
        import dropbox
        dbx = dropbox.Dropbox(self.access_token)
        full_path = f"{self.folder_path}/{remote_path}"
        dbx.files_delete_v2(full_path)
        return True

    async def verify_connection(self) -> bool:
        try:
            import dropbox
            dbx = dropbox.Dropbox(self.access_token)
            dbx.users_get_current_account()
            return True
        except Exception:
            return False

    async def get_download_url(self, remote_path: str, expires: int = 3600) -> str:
        import dropbox
        dbx = dropbox.Dropbox(self.access_token)
        full_path = f"{self.folder_path}/{remote_path}"
        link = dbx.files_get_temporary_link(full_path)
        return link.link


def get_storage_backend(storage_connection) -> StorageBackend:
    """Factory function to create the appropriate storage backend."""
    from app.models.models import StorageType

    if storage_connection.storage_type == StorageType.S3:
        return S3Backend(
            credentials_encrypted=storage_connection.credentials_encrypted,
            bucket_name=storage_connection.bucket_name,
            region=storage_connection.bucket_region or "us-east-1",
        )
    elif storage_connection.storage_type == StorageType.MANAGED_S3:
        return ManagedS3Backend(
            bucket_name=storage_connection.bucket_name,
            region=storage_connection.bucket_region or "us-east-1",
        )
    elif storage_connection.storage_type == StorageType.DROPBOX:
        return DropboxBackend(
            credentials_encrypted=storage_connection.credentials_encrypted,
            folder_path=storage_connection.dropbox_folder_path or "/EventVault",
        )
    else:
        raise ValueError(f"Unknown storage type: {storage_connection.storage_type}")
