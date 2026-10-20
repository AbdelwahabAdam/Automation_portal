"""Our copy of Daftra's client categories (التصنيف), each with where its clients live."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"


def upgrade():
    op.create_table(
        "client_categories",
        # Daftra's own id for the category
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("emirate", sa.String(50), nullable=True),
        sa.Column("area", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("client_categories")
