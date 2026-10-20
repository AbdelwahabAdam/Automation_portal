"""Link users to Daftra staff, and keep what approving a request created in Daftra."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"

REQUEST_COLUMNS = [
    sa.Column("daftra_client_id", sa.Integer(), nullable=True),
    sa.Column("daftra_invoice_id", sa.Integer(), nullable=True),
    sa.Column("daftra_invoice_no", sa.String(30), nullable=True),
    sa.Column("daftra_payment_id", sa.Integer(), nullable=True),
    sa.Column("daftra_receipt_no", sa.String(30), nullable=True),
    sa.Column("daftra_error", sa.Text(), nullable=True),
    sa.Column("daftra_synced_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade():
    op.add_column("users", sa.Column("daftra_staff_id", sa.Integer(), nullable=True))
    for column in REQUEST_COLUMNS:
        op.add_column("requests", column)


def downgrade():
    for column in reversed(REQUEST_COLUMNS):
        op.drop_column("requests", column.name)
    op.drop_column("users", "daftra_staff_id")
