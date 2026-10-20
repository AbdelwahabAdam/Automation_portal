"""Mark the products offered as items on طلب صيانة وتبديل, by their group (الفلاتر، قطع الغيار، …)."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"


def upgrade():
    op.add_column("products", sa.Column("maintenance_group", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("products", "maintenance_group")
