"""When Daftra last left a request's payment unanswered.

Daftra has recorded a payment a minute after the portal stopped waiting for its answer, and an
approval tried again in that minute could not see it yet and paid twice (request 204, invoice
06651). The time is kept so the next try waits for it instead (invoicing.invoice.make_payment).
Empty for every request until that happens to it.
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"


def upgrade():
    op.add_column("requests", sa.Column("payment_unanswered_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("requests", "payment_unanswered_at")
