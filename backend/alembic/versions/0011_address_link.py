"""A Google Maps link for an address, e.g. https://maps.app.goo.gl/..."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade():
    op.add_column("addresses", sa.Column("link", sa.String(600), nullable=False, server_default=""))


def downgrade():
    op.drop_column("addresses", "link")
