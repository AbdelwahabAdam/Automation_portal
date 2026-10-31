"""The product behind «اعمال باسكو» on اعمال اضافية (قسم الفنيات).

The form offers its works by Daftra id, and only those the catalog holds: on a server whose catalog
lacks 433 it offers three of its four. An invoice line needs the product row, so the form cannot
do without it. Its price on the form is the form's own (TECH_SERVICE_PRICES); this one is what it
costs anywhere else.

A catalog that already has it is left as it is, and a downgrade leaves it there: by then it may be
on requests.
"""

from alembic import op

revision = "0022"
down_revision = "0021"

ADD_PRODUCT = """
    INSERT INTO products (name, name_ar, description, unit_price, price_includes_tax, tax_rate, is_active,
                          daftra_id, product_code)
    VALUES ('interlocking paving Removel $ Breaking Service', '', '', 10, true, 0.05, true, 433, '2016')
    ON CONFLICT DO NOTHING
"""


def upgrade():
    op.execute(ADD_PRODUCT)


def downgrade():
    pass
