"""One record per job run, for any job, and the mark that says Daftra has an address.

`job_runs` replaces `sync_runs`, which only knew about the two Daftra lists. The history is
copied across, with the old "kind" becoming the job's name ("products" -> "sync_products").

This release only adds: `sync_runs` is left in place and is dropped by the release after it, once
this one is confirmed live. A deploy that rolls the code back can put the old code back but not
the database, so nothing a release removes may still be read by the release before it.

`addresses.in_daftra` says whether Daftra has taken that address. An address the portal saved and
Daftra refused used to be wiped by the nightly sync, which emptied both tables and built them
again; it is now kept, marked false, and offered to Daftra again at the start of the next sync.
Every address that exists now came from Daftra or was accepted by it, so they all start true.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019"
down_revision = "0018"

# The old sync_runs.kind as the job it is now
NAMES = {"products": "sync_products", "clients": "sync_clients"}


def upgrade():
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(40), nullable=False, index=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("started_by_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_by_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=False, server_default=""),
    )
    # The history of the «المزامنة مع دفترة» page, so it does not start empty
    whens = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in NAMES.items())
    op.execute(f"""
        INSERT INTO job_runs (id, name, status, started_by_id, started_by_name, started_at,
                              finished_at, summary, error)
        SELECT id, CASE kind {whens} ELSE kind END, status, started_by_id, started_by_name,
               started_at, finished_at, summary, error
        FROM sync_runs
    """)
    op.execute("SELECT setval('job_runs_id_seq', COALESCE((SELECT max(id) FROM job_runs), 1))")

    op.add_column("addresses",
                  sa.Column("in_daftra", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("addresses", "in_daftra")
    op.drop_table("job_runs")
