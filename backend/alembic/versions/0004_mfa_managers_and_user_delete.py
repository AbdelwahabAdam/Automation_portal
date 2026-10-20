"""Two-step login, department managers, and audit entries that outlive a deleted user."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0004"
down_revision = "0003"


def upgrade():
    op.add_column("users", sa.Column("totp_secret", sa.String(64)))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("users", sa.Column("totp_last_step", sa.Integer, nullable=False, server_default="0"))
    op.add_column("users", sa.Column("manages", ARRAY(sa.String(30)), nullable=False, server_default="{}"))
    # Deleting a user keeps their audit entries, which carry the username as text
    op.drop_constraint("audit_log_user_id_fkey", "audit_log", type_="foreignkey")
    op.create_foreign_key("audit_log_user_id_fkey", "audit_log", "users", ["user_id"], ["id"], ondelete="SET NULL")


def downgrade():
    op.drop_constraint("audit_log_user_id_fkey", "audit_log", type_="foreignkey")
    op.create_foreign_key("audit_log_user_id_fkey", "audit_log", "users", ["user_id"], ["id"])
    op.drop_column("users", "manages")
    op.drop_column("users", "totp_last_step")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
