"""A product's SKU in the final catalog workbook, so re-imports can match by it instead of by name."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade():
    op.add_column("products", sa.Column("sku", sa.String(20), nullable=True))
    op.create_unique_constraint("uq_products_sku", "products", ["sku"])


def downgrade():
    op.drop_constraint("uq_products_sku", "products", type_="unique")
    op.drop_column("products", "sku")
