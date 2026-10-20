"""Manager review of requests: returned and approved statuses, revisions, and each request's history."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade():
    # A request is now draft -> submitted -> returned (back to the salesperson) or approved
    op.add_column("requests", sa.Column("revision", sa.Integer, nullable=False, server_default="0"))
    op.add_column("requests", sa.Column("returned_reason", sa.Text))
    op.add_column("requests", sa.Column("reviewed_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("requests", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_table(
        "request_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("username", sa.String(120), nullable=False, server_default=""),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, server_default="0"),
        sa.Column("note", sa.Text),
    )
    op.create_index("ix_request_events_request_id", "request_events", ["request_id"])
    # History for requests made before this: when they were created and, if so, sent
    op.execute("UPDATE requests SET revision = 1 WHERE status <> 'draft'")
    op.execute(
        "INSERT INTO request_events (request_id, at, user_id, username, kind, revision) "
        "SELECT r.id, r.created_at, r.created_by_id, coalesce(nullif(u.full_name, ''), u.username), 'created', 0 "
        "FROM requests r JOIN users u ON u.id = r.created_by_id"
    )
    op.execute(
        "INSERT INTO request_events (request_id, at, user_id, username, kind, revision) "
        "SELECT r.id, coalesce(r.submitted_at, r.updated_at), r.created_by_id, coalesce(nullif(u.full_name, ''), u.username), "
        "'submitted', 1 FROM requests r JOIN users u ON u.id = r.created_by_id WHERE r.status <> 'draft'"
    )


def downgrade():
    op.execute("UPDATE requests SET status = 'submitted' WHERE status IN ('returned', 'approved')")
    op.drop_table("request_events")
    op.drop_column("requests", "reviewed_at")
    op.drop_column("requests", "reviewed_by_id")
    op.drop_column("requests", "returned_reason")
    op.drop_column("requests", "revision")
