"""Draw the أمر شغل PDF again for requests approved before the form was redesigned.

Usage: python -m app.redraw_work_orders 42 43     the requests with these ids
       python -m app.redraw_work_orders --all     every approved request that has one
       python -m app.redraw_work_orders --all -n  what it would do, without writing

The portal draws that PDF itself (app/templates/pdf/work_order.html) and saves it once, when the
request is approved, so a change to the template leaves every earlier request showing the old
design. This replaces the file in place: same attachment, same name, new contents.

The title and the dates are read back from the work order in Daftra, since they were worked out
at approval time and only Daftra keeps them. The lines and the custom field values are built
from the request and today's products table, so a product renamed or merged since the request
was approved reads by its current name. Safe to run again.
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import daftra, printouts
from .config import UPLOAD_DIR
from .daftra import DaftraError
from .daftra_sync.common import WORK_ORDER_ATTACHMENT_FIELD
from .daftra_sync.work_order import draw_work_order
from .database import SessionLocal
from .models import Request


def redraw(request: Request, db, dry_run: bool = False) -> str:
    """Replaces the request's work order PDF with one drawn from the current template,
    and says what happened, for the line printed about this request."""
    attachment = next((a for a in request.attachments if a.field == WORK_ORDER_ATTACHMENT_FIELD), None)
    if attachment is None:
        return "no work order PDF on it"
    if request.daftra_work_order_id is None:
        return "no work order in Daftra"
    if request.reviewed_by is None:
        return "no approving manager, whose name the PDF carries"
    path = UPLOAD_DIR / str(request.id) / attachment.stored_name
    if not path.exists():
        return f"its file is missing ({path})"

    try:
        row = daftra.get(f"work_orders/{request.daftra_work_order_id}.json").get("data", {}).get("WorkOrder", {})
    except DaftraError as error:
        return f"Daftra: {error}"
    # Only for the title, when the work order in Daftra has none of its own
    invoice = {}
    if request.daftra_invoice_id is not None and not row.get("title"):
        try:
            invoice = daftra.get(f"invoices/{request.daftra_invoice_id}.json").get("data", {}).get("Invoice", {})
        except DaftraError:
            pass

    try:
        content = draw_work_order(request, row, invoice, request.reviewed_by, db)
    except printouts.PrintoutError as error:
        return f"could not be drawn: {error}"
    was = attachment.size
    if dry_run:
        return f"would redraw {attachment.filename}: {was:,} → {len(content):,} bytes"
    path.write_bytes(content)
    attachment.size = len(content)
    db.commit()
    return f"redrawn {attachment.filename}: {was:,} → {len(content):,} bytes"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", type=int, help="the request ids to redraw")
    parser.add_argument("--all", action="store_true", help="every approved request that has a work order PDF")
    parser.add_argument("-n", "--dry-run", action="store_true", help="say what would change, write nothing")
    args = parser.parse_args()
    if bool(args.ids) == args.all:
        parser.error("give request ids or --all, not both and not neither")

    with SessionLocal() as db:
        query = select(Request).options(selectinload(Request.attachments)).order_by(Request.id)
        if args.all:
            query = query.where(Request.status == "approved")
        else:
            query = query.where(Request.id.in_(args.ids))
        requests = db.scalars(query).all()
        found = {request.id for request in requests}
        for missing in sorted(set(args.ids) - found):
            print(f"  {missing}: no such request")
        done = 0
        for request in requests:
            result = redraw(request, db, args.dry_run)
            # --all walks every approved request, so the ones with nothing to redraw stay quiet
            if args.all and result == "no work order PDF on it":
                continue
            print(f"  {request.id}: {result}")
            if result.startswith(("redrawn", "would redraw")):
                done += 1
    print(f"{done} work order PDF(s) {'to redraw' if args.dry_run else 'redrawn'}")


if __name__ == "__main__":
    main()
