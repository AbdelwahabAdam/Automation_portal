"""User email, and no password until an invited user sets one."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    # Users created before this have no email until an admin adds it
    op.add_column("users", sa.Column("email", sa.String(254)))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.alter_column("users", "password_hash", nullable=True)


def downgrade():
    # Invited users who never set a password get an unusable one
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", nullable=False)
    op.drop_index("ix_users_email", "users")
    op.drop_column("users", "email")
