"""The tables as they were before migrations were introduced."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "0001"
down_revision = None


def upgrade():
    # Databases created before migrations existed already have these tables
    if sa.inspect(op.get_bind()).has_table("users"):
        return
    now = sa.func.now()
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("roles", ARRAY(sa.String(30)), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("form_type", sa.String(50), nullable=False),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_requests_form_type", "requests", ["form_type"])
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_created_by_id", "requests", ["created_by_id"])
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_index("ix_attachments_request_id", "attachments", ["request_id"])


def downgrade():
    op.drop_table("attachments")
    op.drop_table("requests")
    op.drop_table("users")
