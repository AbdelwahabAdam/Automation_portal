"""Clients, kept locally from Daftra's client export so a form can look one up without calling Daftra."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade():
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("daftra_id", sa.Integer, nullable=False, unique=True),
        sa.Column("client_code", sa.String(10), nullable=False, unique=True),
        sa.Column("customer_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("phone2", sa.String(20), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("emirate", sa.String(50), nullable=False, server_default=""),
        sa.Column("area", sa.String(100), nullable=False, server_default=""),
        sa.Column("street", sa.String(200), nullable=False, server_default=""),
        sa.Column("house", sa.String(100), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_clients_phone", "clients", ["phone"])


def downgrade():
    op.drop_table("clients")
