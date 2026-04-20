"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enum types ---
    op.execute(sa.text(
        "CREATE TYPE event_type_enum AS ENUM ('wedding', 'graduation', 'birthday', 'corporate', 'other')"
    ))
    op.execute(sa.text(
        "CREATE TYPE event_status_enum AS ENUM ('draft', 'active', 'archived')"
    ))
    op.execute(sa.text(
        "CREATE TYPE event_tier_enum AS ENUM ('free', 'standard', 'premium')"
    ))
    op.execute(sa.text(
        "CREATE TYPE event_tier_name_enum AS ENUM ('free', 'standard', 'premium')"
    ))
    op.execute(sa.text(
        "CREATE TYPE storage_type_enum AS ENUM ('dropbox', 's3', 'managed_s3')"
    ))
    op.execute(sa.text(
        "CREATE TYPE upload_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed')"
    ))
    op.execute(sa.text(
        "CREATE TYPE payment_status_enum AS ENUM ('pending', 'succeeded', 'failed', 'refunded')"
    ))

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- event_tiers ---
    op.create_table(
        "event_tiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Enum("free", "standard", "premium", name="event_tier_name_enum", create_type=False), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("max_uploads", sa.Integer(), nullable=False),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=False),
        sa.Column("max_total_storage_gb", sa.Integer(), nullable=False),
        sa.Column("allows_video", sa.Boolean(), nullable=False),
        sa.Column("allows_custom_branding", sa.Boolean(), nullable=False),
        sa.Column("managed_s3_monthly_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_event_tiers_name"),
    )

    # --- events ---
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("event_type", sa.Enum("wedding", "graduation", "birthday", "corporate", "other", name="event_type_enum", create_type=False), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Enum("draft", "active", "archived", name="event_status_enum", create_type=False), nullable=False, server_default="draft"),
        sa.Column("tier", sa.Enum("free", "standard", "premium", name="event_tier_enum", create_type=False), nullable=False, server_default="free"),
        sa.Column("upload_limit_mb", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("total_storage_limit_gb", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("guest_pin", sa.String(6), nullable=True),
        sa.Column("allow_video", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_photo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("cover_image_url", sa.String(1024), nullable=True),
        sa.Column("welcome_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_user_status", "events", ["user_id", "status"])

    # --- event_links ---
    op.create_table(
        "event_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("short_code", sa.String(16), nullable=False),
        sa.Column("qr_code_path", sa.String(1024), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("click_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("short_code", name="uq_event_links_short_code"),
    )
    op.create_index("ix_event_links_event_id", "event_links", ["event_id"])
    op.create_index("ix_event_links_short_code", "event_links", ["short_code"], unique=True)

    # --- storage_connections ---
    op.create_table(
        "storage_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_type", sa.Enum("dropbox", "s3", "managed_s3", name="storage_type_enum", create_type=False), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("bucket_name", sa.String(255), nullable=True),
        sa.Column("bucket_region", sa.String(63), nullable=True),
        sa.Column("dropbox_folder_path", sa.String(1024), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("event_id", name="uq_storage_connections_event_id"),
    )

    # --- uploads ---
    op.create_table(
        "uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guest_name", sa.String(255), nullable=True),
        sa.Column("guest_device_id", sa.String(255), nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", name="upload_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("thumbnail_path", sa.String(1024), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("exif_taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_uploads_event_id", "uploads", ["event_id"])
    op.create_index("ix_uploads_event_status", "uploads", ["event_id", "status"])
    op.create_index("ix_uploads_event_created", "uploads", ["event_id", "created_at"])

    # --- payments ---
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("status", sa.Enum("pending", "succeeded", "failed", "refunded", name="payment_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("stripe_payment_intent_id", name="uq_payments_stripe_intent"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_event_id", "payments", ["event_id"])

    # --- Seed event tiers ---
    import uuid
    op.execute(sa.text("""
        INSERT INTO event_tiers (id, name, price_cents, max_uploads, max_file_size_mb, max_total_storage_gb,
                                 allows_video, allows_custom_branding, managed_s3_monthly_cents)
        VALUES
            (:free_id,     'free',     0,    50,   10,   1,   false, false, 0),
            (:std_id,      'standard', 1500, 500,  50,   10,  true,  false, 999),
            (:premium_id,  'premium',  4900, -1,   500,  100, true,  true,  999)
    """), {
        "free_id": str(uuid.uuid4()),
        "std_id": str(uuid.uuid4()),
        "premium_id": str(uuid.uuid4()),
    })


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("uploads")
    op.drop_table("storage_connections")
    op.drop_table("event_links")
    op.drop_table("events")
    op.drop_table("event_tiers")
    op.drop_table("users")

    op.execute(sa.text("DROP TYPE IF EXISTS payment_status_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS upload_status_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS storage_type_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS event_tier_name_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS event_tier_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS event_status_enum"))
    op.execute(sa.text("DROP TYPE IF EXISTS event_type_enum"))
