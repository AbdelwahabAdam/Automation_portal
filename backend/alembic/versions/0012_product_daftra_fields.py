"""A fuller Daftra snapshot on each product: id, code, barcode, buy price, stock, category, brand."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"


def upgrade():
    op.add_column("products", sa.Column("daftra_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_products_daftra_id", "products", ["daftra_id"])
    op.add_column("products", sa.Column("product_code", sa.String(50), nullable=True))
    op.add_column("products", sa.Column("barcode", sa.String(50), nullable=True))
    op.add_column("products", sa.Column("buy_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("stock_balance", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("category", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("brand", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("products", "brand")
    op.drop_column("products", "category")
    op.drop_column("products", "stock_balance")
    op.drop_column("products", "buy_price")
    op.drop_column("products", "barcode")
    op.drop_column("products", "product_code")
    op.drop_constraint("uq_products_daftra_id", "products", type_="unique")
    op.drop_column("products", "daftra_id")
