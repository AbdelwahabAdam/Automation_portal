"""طلب بيع - دفع إلكتروني (form key online_sale): the same access as طلب بيع لعميل جديد.

Every role that may fill, view or review new_sale is given the same on online_sale. Roles change
nothing else, and a role made later is given it by hand like any form. Requests that wait for
their payment get the status «awaiting_payment», which needs no change to the table.
"""

from alembic import op

revision = "0027"
down_revision = "0026"

GIVE = """
    UPDATE roles SET permissions = array_append(permissions, 'form.online_sale.{does}')
    WHERE 'form.new_sale.{does}' = ANY(permissions) AND NOT 'form.online_sale.{does}' = ANY(permissions)
"""


def upgrade():
    for does in ("submit", "view", "review"):
        op.execute(GIVE.format(does=does))


def downgrade():
    for does in ("submit", "view", "review"):
        op.execute(f"UPDATE roles SET permissions = array_remove(permissions, 'form.online_sale.{does}')")
