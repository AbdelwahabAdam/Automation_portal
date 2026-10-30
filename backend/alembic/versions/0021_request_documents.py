"""A row per Daftra document an approved request created, instead of seven columns on the request.

A form that creates something else — a credit note for a return, an estimate for a quotation —
now adds a kind, not a column.

Only adds: the seven columns stay and keep being written, because the release before this one
reads them and a deploy that rolls the code back can put the old code back but not the database.
The release after this one, once this is confirmed live, stops writing them and drops them.

`daftra_error` and `daftra_synced_at` stay on the request: they are about the approval, not about
one document.
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"

# The column pair each kind used to live in
COLUMNS = [
    ("client", "daftra_client_id", None),
    ("invoice", "daftra_invoice_id", "daftra_invoice_no"),
    ("payment", "daftra_payment_id", "daftra_receipt_no"),
    ("work_order", "daftra_work_order_id", "daftra_work_order_no"),
]


def upgrade():
    op.create_table(
        "request_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("requests.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("external_id", sa.Integer, nullable=False),
        sa.Column("number", sa.String(30), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Deferred: a step that lets go of one document and saves another of the same kind in
        # one transaction would otherwise insert before the delete and hit this key
        sa.UniqueConstraint("request_id", "kind", name="uq_request_documents_kind",
                            deferrable=True, initially="DEFERRED"),
    )
    # What every approved request has already created, in the order the steps run
    for kind, id_column, number_column in COLUMNS:
        number = f"COALESCE({number_column}, '')" if number_column else "''"
        op.execute(f"""
            INSERT INTO request_documents (request_id, kind, external_id, number, created_at)
            SELECT id, '{kind}', {id_column}, {number}, COALESCE(daftra_synced_at, created_at)
            FROM requests
            WHERE {id_column} IS NOT NULL
        """)


def downgrade():
    op.drop_table("request_documents")
