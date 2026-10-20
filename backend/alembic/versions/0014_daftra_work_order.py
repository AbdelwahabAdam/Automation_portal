"""The Daftra work order (أمر الشغل) an approved request created, if it asked for one."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"


def upgrade():
    op.add_column("requests", sa.Column("daftra_work_order_id", sa.Integer(), nullable=True))
    op.add_column("requests", sa.Column("daftra_work_order_no", sa.String(30), nullable=True))


def downgrade():
    op.drop_column("requests", "daftra_work_order_no")
    op.drop_column("requests", "daftra_work_order_id")
