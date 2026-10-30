"""What approving a request created in Daftra, as one row per document.

A form that creates something else — a credit note for a return, an estimate for a quotation —
adds a kind, not a column. The seven columns are still written while the release before this one
could still be rolled back to; the release after it drops them.
"""

from sqlalchemy import text

from app.modules.models import Request, RequestDocument

from ... import seed
from ...conftest import auth
from ...seed import submitted_sale


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision},
                       headers=auth(user))


def test_approving_records_each_document_once(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200

    request = db.get(Request, request_id)
    db.refresh(request)
    kinds = {row.kind: row for row in request.documents}
    assert set(kinds) == {"client", "invoice", "payment", "work_order"}
    # Each carries Daftra's id, and the number people read where there is one
    assert kinds["invoice"].external_id == request.daftra_invoice_id
    assert kinds["invoice"].number == request.daftra_invoice_no
    assert kinds["payment"].number == request.daftra_receipt_no
    assert kinds["work_order"].number == request.daftra_work_order_no
    assert kinds["client"].number == ""


def test_the_old_columns_are_still_written(client, db, fake_daftra, sales, manager):
    """The release before this one reads them, and a rollback can put the old code back but not
    the database. The release after this one stops writing them and drops them."""
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    row = db.execute(text(
        "SELECT daftra_client_id, daftra_invoice_id, daftra_invoice_no, daftra_payment_id, "
        "daftra_receipt_no, daftra_work_order_id, daftra_work_order_no FROM requests WHERE id = :id"
    ), {"id": request_id}).one()
    assert all(value is not None for value in row)


def test_the_api_still_answers_the_three_numbers(client, db, fake_daftra, sales, manager):
    """The screens read these, so they must look exactly as they did — now from the table."""
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    approve(client, manager, request_id)
    out = client.get(f"/api/requests/{request_id}", headers=auth(sales)).json()
    assert out["daftra_invoice_no"] and out["daftra_receipt_no"] and out["daftra_work_order_no"]
    queue = client.get("/api/review/requests", headers=auth(manager)).json()
    row = next(r for r in queue if r["id"] == request_id)
    assert row["daftra_invoice_no"] == out["daftra_invoice_no"]


def test_one_of_each_kind_per_request(client, db, fake_daftra, sales, manager):
    """Approving again after a failure carries on; it never adds a second invoice row."""
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    fake_daftra.fail_once = "/api2/invoice_payments.json"
    assert approve(client, manager, request_id).status_code in (409, 502)
    # The invoice was made; the payment was not
    request = db.get(Request, request_id)
    db.refresh(request)
    assert {row.kind for row in request.documents} == {"client", "invoice"}

    assert approve(client, manager, request_id).status_code == 200
    db.refresh(request)
    kinds = [row.kind for row in request.documents]
    assert len(kinds) == len(set(kinds)), "a kind was recorded twice"
    assert set(kinds) == {"client", "invoice", "payment", "work_order"}


def test_letting_go_of_another_portals_invoice_leaves_one_row(client, db, fake_daftra, sales, manager):
    """The kind's row is replaced, not doubled — the unique key is deferred so the new row may be
    inserted before the old one is deleted."""
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    theirs = fake_daftra.add_invoice(client_id=4053, total=999.0)
    request = db.get(Request, request_id)
    request.save_document("invoice", theirs, "09999")
    db.commit()

    assert approve(client, manager, request_id).status_code == 200
    db.refresh(request)
    invoices = [row for row in request.documents if row.kind == "invoice"]
    assert len(invoices) == 1 and invoices[0].external_id != theirs


def test_the_documents_go_with_the_request(client, db, sales):
    """Deleting a draft takes its documents with it (there are none, but the cascade is the point)."""
    request_id = client.post("/api/requests", json={"form_type": "new_sale", "data": {}, "action": "draft"},
                             headers=auth(sales)).json()["id"]
    request = db.get(Request, request_id)
    request.save_document("client", 4053)
    db.commit()
    assert db.query(RequestDocument).filter_by(request_id=request_id).count() == 1
    assert client.delete(f"/api/requests/{request_id}", headers=auth(sales)).status_code == 204
    assert db.query(RequestDocument).filter_by(request_id=request_id).count() == 0
