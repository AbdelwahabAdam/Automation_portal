"""Draw the عرض سعر PDF for approved quotations: the ones approved before the portal drew it, which
have none, and — after the template changes — the ones drawn already.

Usage: python -m app.jobs estimate_pdfs 149 150     the requests with these ids
       python -m app.jobs estimate_pdfs --all       every approved request with an estimate in Daftra
       python -m app.jobs estimate_pdfs --all -n    what it would do, without writing

Until 2026-11-14 the portal downloaded the estimate's PDF from Daftra, which never worked: the link
Daftra gives an estimate does not open. So no quotation approved before then has its PDF. This
draws it from the estimate as Daftra holds it today. A request with one already has its file
replaced in place: same attachment, same name, new contents. Safe to run again.
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.config import UPLOAD_DIR
from ..core.database import SessionLocal
from ..integrations.daftra import DaftraError
from ..modules.invoicing import (ESTIMATE_ATTACHMENT_FIELD, draw_estimate, get_estimate, printouts,
                                 save_estimate_pdf)
from ..modules.models import Request, RequestDocument
from .registry import job


def draw(request: Request, db, dry_run: bool = False) -> str:
    """Draws the request's estimate PDF, adding it or replacing the one it has, and says what happened."""
    if request.daftra_estimate_id is None:
        return "no estimate in Daftra"
    try:
        estimate = get_estimate(request.daftra_estimate_id)
    except DaftraError as error:
        return f"Daftra: {error}"
    attachment = next((a for a in request.attachments if a.field == ESTIMATE_ATTACHMENT_FIELD), None)

    if attachment is None:
        if dry_run:
            return f"would add the PDF of estimate {estimate.get('no') or request.daftra_estimate_no}"
        if not save_estimate_pdf(request, estimate, db):
            return "could not be drawn"
        db.commit()
        return f"added the PDF of estimate {estimate.get('no') or request.daftra_estimate_no}"

    path = UPLOAD_DIR / str(request.id) / attachment.stored_name
    try:
        content = draw_estimate(request, estimate)
    except printouts.PrintoutError as error:
        return f"could not be drawn: {error}"
    if dry_run:
        return f"would redraw {attachment.filename}: {attachment.size:,} → {len(content):,} bytes"
    was = attachment.size
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    attachment.size = len(content)
    db.commit()
    return f"redrawn {attachment.filename}: {was:,} → {len(content):,} bytes"


@job("estimate_pdfs", label="رسم ملفات عروض الأسعار", recorded=False,
     about="Draws the estimate (عرض سعر) PDFs for approved quotations")
def _run(db, who):
    """This one is a command line only: `python -m app.jobs estimate_pdfs …`."""
    raise SystemExit("Run it as: python -m app.jobs estimate_pdfs [options]")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", type=int, help="the request ids to draw")
    parser.add_argument("--all", action="store_true", help="every approved request with an estimate in Daftra")
    parser.add_argument("-n", "--dry-run", action="store_true", help="say what would change, write nothing")
    args = parser.parse_args()
    if bool(args.ids) == args.all:
        parser.error("give request ids or --all, not both and not neither")

    with SessionLocal() as db:
        query = select(Request).options(selectinload(Request.attachments)).order_by(Request.id)
        if args.all:
            query = query.where(Request.status == "approved", Request.documents.any(RequestDocument.kind == "estimate"))
        else:
            query = query.where(Request.id.in_(args.ids))
        requests = db.scalars(query).all()
        for missing in sorted(set(args.ids) - {request.id for request in requests}):
            print(f"  {missing}: no such request")
        done = 0
        for request in requests:
            result = draw(request, db, args.dry_run)
            print(f"  {request.id}: {result}")
            if result.startswith(("added", "redrawn", "would")):
                done += 1
    print(f"{done} estimate PDF(s) {'to draw' if args.dry_run else 'drawn'}")


if __name__ == "__main__":
    main()
