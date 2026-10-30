"""Access per form: a role holds permissions, not pages.

Nobody gains or loses anything on the day:

- a role with `sales.new_request` or `sales.my_requests` gets `form.<key>.submit` for each of the
  visible forms, because those pages opened all of them;
- a role with an admin page keeps it under its new key (`admin.permissions` -> `admin.roles`,
  `admin.daftra_sync` -> `admin.sync`);
- the pages of the hidden departments are dropped — nobody could open them;
- users who manage `sales` get a new role, «مراجعة جميع النماذج», with `review` on every form and
  `submit` on the visible ones, because a manager opened every sales page and المراجعة showed
  every form.

Only adds: `roles.pages` and `users.manages` are left in place and dropped by the release after
this one, once this one is confirmed live. A deploy that rolls the code back can put the old code
back but not the database.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0020"
down_revision = "0019"

# Every form, and which of them a new request can be made from. Written out rather than imported,
# because a migration must keep working when the code has moved on.
FORMS = [
    "new_sale", "contract_renewal", "maintenance", "balance_payment", "quotation", "quote_to_invoice",
    "order_addition", "order_modification", "return_refund", "tech_cash_collection", "reinstallation",
    "data_entry_error", "pre_sale_inspection", "installation_completed", "contract_service_done",
    "open_ticket", "close_ticket", "daily_visits", "tech_extra_works",
]
VISIBLE = ["new_sale", "contract_renewal", "maintenance", "balance_payment", "quotation", "tech_extra_works"]
# The pages that opened every visible form
FILL_PAGES = ("sales.new_request", "sales.my_requests")
ADMIN_PAGES = {
    "admin.users": "admin.users",
    "admin.permissions": "admin.roles",
    "admin.audit": "admin.audit",
    "admin.catalog": "admin.catalog",
    "admin.daftra_sync": "admin.sync",
    "admin.order_sources": "admin.order_sources",
    "admin.mail": "admin.mail",
}
REVIEWER_ROLE = "مراجعة جميع النماذج"


def _keys_for(pages: list[str]) -> list[str]:
    keys = []
    if set(pages) & set(FILL_PAGES):
        keys += [f"form.{key}.submit" for key in VISIBLE]
    if "sales.review" in pages:
        # A page only a department's manager had; kept here in case a role carries it
        keys += [f"form.{key}.review" for key in FORMS]
    keys += [ADMIN_PAGES[page] for page in pages if page in ADMIN_PAGES]
    return sorted(set(keys))


def upgrade():
    op.add_column("roles", sa.Column("permissions", ARRAY(sa.String(80)), nullable=False,
                                     server_default=sa.text("'{}'")))
    connection = op.get_bind()

    for role_id, pages in connection.execute(sa.text("SELECT id, pages FROM roles")).all():
        keys = _keys_for(list(pages or []))
        if keys:
            connection.execute(sa.text("UPDATE roles SET permissions = :keys WHERE id = :id"),
                               {"keys": keys, "id": role_id})

    # Today's department managers: a manager opened every sales page, and المراجعة showed every form
    managers = connection.execute(
        sa.text("SELECT id FROM users WHERE 'sales' = ANY(manages) AND NOT is_admin")
    ).scalars().all()
    if managers:
        keys = sorted({f"form.{key}.review" for key in FORMS} | {f"form.{key}.submit" for key in VISIBLE})
        role_id = connection.execute(
            sa.text("INSERT INTO roles (name, pages, permissions) VALUES (:name, '{}', :keys) "
                    "ON CONFLICT (name) DO UPDATE SET permissions = :keys RETURNING id"),
            {"name": REVIEWER_ROLE, "keys": keys},
        ).scalar()
        for user_id in managers:
            connection.execute(
                sa.text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id) "
                        "ON CONFLICT DO NOTHING"),
                {"user_id": user_id, "role_id": role_id},
            )


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM roles WHERE name = :name"), {"name": REVIEWER_ROLE})
    op.drop_column("roles", "permissions")
