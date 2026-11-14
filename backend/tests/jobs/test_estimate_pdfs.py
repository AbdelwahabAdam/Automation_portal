"""The عرض سعر PDF on an approved quotation, and app.jobs estimate_pdfs for the ones approved before
the portal drew it (every one until 2026-11-14: Daftra's link for an estimate's PDF does not open)."""

from app.core.config import UPLOAD_DIR
from app.integrations import daftra
from app.jobs.estimate_pdfs import draw
from app.modules.models import Attachment, Request

from .. import seed
from ..conftest import auth
from ..seed import submitted_sale


def approved_quotation(client, db, sales, manager) -> Request:
    seed.catalog(db)
    request_id = seed.submitted_quotation(client, db, sales)
    response = client.post(f"/api/review/requests/{request_id}/approve", json={"revision": 1}, headers=auth(manager))
    assert response.status_code == 200, response.json()
    request = db.get(Request, request_id)
    db.refresh(request)
    return request


def estimate_pdf(request) -> Attachment | None:
    return next((a for a in request.attachments if a.field == "daftra_estimate"), None)


def test_approving_a_quotation_draws_its_pdf_without_asking_daftra_for_one(client, db, fake_daftra, sales,
                                                                            manager, monkeypatch):
    asked = []
    monkeypatch.setattr(daftra, "invoice_pdf", lambda *args: asked.append(args) or b"%PDF daftra's")
    request = approved_quotation(client, db, sales, manager)
    pdf = estimate_pdf(request)
    content = (UPLOAD_DIR / str(request.id) / pdf.stored_name).read_bytes()
    assert content.startswith(b"%PDF") and len(content) > 1000
    assert pdf.filename.startswith("عرض سعر") and pdf.filename.endswith(".pdf")
    assert asked == []


def test_a_quotation_approved_without_its_pdf_gets_one(client, db, fake_daftra, sales, manager):
    request = approved_quotation(client, db, sales, manager)
    # As every quotation approved before 2026-11-14 is: no PDF on it
    db.delete(estimate_pdf(request))
    db.commit()
    db.refresh(request)

    assert draw(request, db, dry_run=True).startswith("would add")
    db.refresh(request)
    assert estimate_pdf(request) is None

    assert draw(request, db).startswith("added the PDF of estimate E")
    db.refresh(request)
    pdf = estimate_pdf(request)
    assert (UPLOAD_DIR / str(request.id) / pdf.stored_name).read_bytes().startswith(b"%PDF")


def test_one_drawn_already_is_replaced_where_it_is(client, db, fake_daftra, sales, manager):
    request = approved_quotation(client, db, sales, manager)
    pdf = estimate_pdf(request)
    path = UPLOAD_DIR / str(request.id) / pdf.stored_name
    path.write_bytes(b"%PDF-1.4 an older design")
    pdf.size = path.stat().st_size
    db.commit()

    assert draw(request, db).startswith("redrawn")
    drawn = path.read_bytes()
    assert drawn.startswith(b"%PDF") and len(drawn) > 1000 and pdf.size == len(drawn)
    assert [a.field for a in request.attachments].count("daftra_estimate") == 1


def test_a_request_with_no_estimate_is_left_alone(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    assert draw(db.get(Request, request_id), db) == "no estimate in Daftra"


def test_all_finds_the_approved_quotations_only(client, db, fake_daftra, sales, manager, monkeypatch, capsys):
    """--all, as it is run on the server after the deploy."""
    import sys
    from app.jobs import estimate_pdfs
    request = approved_quotation(client, db, sales, manager)
    submitted_sale(client, db, sales)
    monkeypatch.setattr(estimate_pdfs, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(sys, "argv", ["estimate_pdfs", "--all", "-n"])
    estimate_pdfs.main()
    out = capsys.readouterr().out
    assert f"  {request.id}: would redraw" in out and "1 estimate PDF(s) to draw" in out
