"""Two-step login by a code sent to email instead of an authenticator app."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    op.alter_column("users", "totp_enabled", new_column_name="mfa_enabled")
    op.drop_column("users", "totp_secret")
    op.drop_column("users", "totp_last_step")
    op.add_column("users", sa.Column("mfa_code_hash", sa.String(64)))
    op.add_column("users", sa.Column("mfa_code_expires", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("mfa_code_sent_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("mfa_code_attempts", sa.Integer, nullable=False, server_default="0"))


def downgrade():
    op.drop_column("users", "mfa_code_attempts")
    op.drop_column("users", "mfa_code_sent_at")
    op.drop_column("users", "mfa_code_expires")
    op.drop_column("users", "mfa_code_hash")
    op.add_column("users", sa.Column("totp_last_step", sa.Integer, nullable=False, server_default="0"))
    op.add_column("users", sa.Column("totp_secret", sa.String(64)))
    # Authenticator keys are gone, so nobody can have the app-based login turned on
    op.execute("UPDATE users SET mfa_enabled = false")
    op.alter_column("users", "mfa_enabled", new_column_name="totp_enabled")
