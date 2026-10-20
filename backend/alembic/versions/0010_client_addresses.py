"""Split a client's address out into its own table, so a client can have more than one."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade():
    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emirate", sa.String(50), nullable=False, server_default=""),
        sa.Column("area", sa.String(100), nullable=False, server_default=""),
        sa.Column("street", sa.String(200), nullable=False, server_default=""),
        sa.Column("house", sa.String(100), nullable=False, server_default=""),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_addresses_client_id", "addresses", ["client_id"])
    op.drop_column("clients", "emirate")
    op.drop_column("clients", "area")
    op.drop_column("clients", "street")
    op.drop_column("clients", "house")


def downgrade():
    op.add_column("clients", sa.Column("emirate", sa.String(50), nullable=False, server_default=""))
    op.add_column("clients", sa.Column("area", sa.String(100), nullable=False, server_default=""))
    op.add_column("clients", sa.Column("street", sa.String(200), nullable=False, server_default=""))
    op.add_column("clients", sa.Column("house", sa.String(100), nullable=False, server_default=""))
    op.drop_table("addresses")
