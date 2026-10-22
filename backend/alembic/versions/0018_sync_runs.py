"""Each refresh of our copies of Daftra's products and clients, with what it changed.

Written by the «المزامنة مع دفترة» admin page and by the nightly client job, so the page shows
when each list was last brought up to date, by whom, and with what result.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018"
down_revision = "0017"


def upgrade():
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("started_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_by_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=False, server_default=""),
    )


def downgrade():
    op.drop_table("sync_runs")
