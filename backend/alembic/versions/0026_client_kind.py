"""نوع العميل and الجنس on our copy of the client list.

The forms' client search fills them in from it, and a change made on a form goes back to Daftra on
approval. Empty until the next client sync reads them from Daftra (المزامنة مع دفترة, or nightly).
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"


def upgrade():
    op.add_column("clients", sa.Column("customer_type", sa.String(20), nullable=False, server_default=""))
    op.add_column("clients", sa.Column("gender", sa.String(20), nullable=False, server_default=""))


def downgrade():
    op.drop_column("clients", "gender")
    op.drop_column("clients", "customer_type")
