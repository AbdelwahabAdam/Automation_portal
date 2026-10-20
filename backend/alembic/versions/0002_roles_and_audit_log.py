"""Roles as lists of pages, the admin flag, and the audit log."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "0002"
down_revision = "0001"

SALES_ROLE = "المبيعات"
SALES_PAGES = ["sales.new_request", "sales.my_requests"]


def upgrade():
    now = sa.func.now()
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("pages", ARRAY(sa.String(60)), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.add_column("users", sa.Column("is_admin", sa.Boolean, nullable=False, server_default="false"))

    # Carry the old text roles over: "admin" becomes the flag, every other one becomes a role
    db = op.get_bind()
    db.execute(sa.text("UPDATE users SET is_admin = true WHERE 'admin' = ANY(roles)"))
    old_roles = db.execute(sa.text("SELECT DISTINCT unnest(roles) FROM users")).scalars().all()
    for old_role in old_roles:
        if old_role == "admin":
            continue
        is_sales = old_role == "sales"
        role_id = db.execute(
            sa.text("INSERT INTO roles (name, pages) VALUES (:name, :pages) RETURNING id"),
            {"name": SALES_ROLE if is_sales else old_role, "pages": SALES_PAGES if is_sales else []},
        ).scalar_one()
        db.execute(
            sa.text("INSERT INTO user_roles (user_id, role_id) SELECT id, :role_id FROM users WHERE :old = ANY(roles)"),
            {"role_id": role_id, "old": old_role},
        )
    op.drop_column("users", "roles")

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer),
        sa.Column("entity_label", sa.String(160), nullable=False),
        sa.Column("before", JSONB),
        sa.Column("after", JSONB),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.String(300), nullable=False),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade():
    op.drop_table("audit_log")
    op.add_column("users", sa.Column("roles", ARRAY(sa.String(30)), nullable=False, server_default="{}"))
    db = op.get_bind()
    db.execute(sa.text("UPDATE users SET roles = ARRAY['admin']::varchar[] WHERE is_admin"))
    db.execute(
        sa.text(
            "UPDATE users SET roles = roles || ARRAY['sales']::varchar[] WHERE id IN "
            "(SELECT user_id FROM user_roles JOIN roles ON roles.id = role_id WHERE name = :name)"
        ),
        {"name": SALES_ROLE},
    )
    op.drop_column("users", "is_admin")
    op.drop_table("user_roles")
    op.drop_table("roles")
