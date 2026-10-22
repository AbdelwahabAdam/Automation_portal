"""The product's image in Daftra, as a file id, for the work order's صورة المنتج (field_30).

Daftra keeps product images and work-order field uploads in one file table, so a product's own
ProductImageS3 id can be written straight into that field.

The column is added only if it is not there already: it was put on the live database by hand
before this migration reached the server, so a plain add would fail there.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("products")}
    if "file_id" not in columns:
        op.add_column("products", sa.Column("file_id", sa.Integer, nullable=True))


def downgrade():
    op.drop_column("products", "file_id")
