"""A product can be sold without a fixed price (بدون سعر ثابت).

Such a product keeps unit_price 0. On طلب بيع and طلب عرض سعر its line asks for the price, and for
the text its invoice line carries, which starts as the product's description. It is a service in
Daftra like every catalog product. Every product there now has a fixed price, so all start false.
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"


def upgrade():
    op.add_column("products", sa.Column("open_price", sa.Boolean, nullable=False, server_default="false"))


def downgrade():
    op.drop_column("products", "open_price")
