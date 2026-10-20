"""Products, packages, and which products each package contains."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
    now = sa.func.now()
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(200), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("price_includes_tax", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=False, server_default="0.05"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(30), unique=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("color", sa.String(40), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_table(
        "product_to_package",
        sa.Column("package_id", sa.Integer, sa.ForeignKey("packages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_includes_tax", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("discount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_product_to_package_product_id", "product_to_package", ["product_id"])


def downgrade():
    op.drop_table("product_to_package")
    op.drop_table("packages")
    op.drop_table("products")
