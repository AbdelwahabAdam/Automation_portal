"""العين becomes an الإمارة of its own on the forms.

Daftra's addresses keep العين inside أبوظبي, and our copy of the client categories was filled that
way. The forms now offer العين as one of the الإمارات (`options.EMIRATES`), so the categories whose
clients are in منطقة العين must say العين — otherwise picking العين offers no التصنيف and picking one
of those categories sets أبوظبي.

Only `client_categories`, which is our cache of Daftra's list: `import_client_categories` fills it
and would set the same values from now on (`CITY_LOCATIONS`), but it reads every client in the
account and is run by hand, so the rows are corrected here instead of waiting for it.

Requests already made are not touched: each holds the الإمارة and المنطقة it was sent with.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"

AIN_AREA = "منطقة العين"
AIN = "العين"
ABU_DHABI = "أبوظبي"


def upgrade():
    op.get_bind().execute(
        sa.text("UPDATE client_categories SET emirate = :ain WHERE area = :area AND emirate = :abu_dhabi"),
        {"ain": AIN, "area": AIN_AREA, "abu_dhabi": ABU_DHABI},
    )


def downgrade():
    op.get_bind().execute(
        sa.text("UPDATE client_categories SET emirate = :abu_dhabi WHERE area = :area AND emirate = :ain"),
        {"ain": AIN, "area": AIN_AREA, "abu_dhabi": ABU_DHABI},
    )
