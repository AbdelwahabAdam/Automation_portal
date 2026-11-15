"""Write the form's ملاحظات into the work order's own ملاحظات field, for work orders the portal made
before that field existed (field_54, added 2026-11-15).

Usage: python -m app.jobs work_order_notes --all -n    what it would do, writing nothing
       python -m app.jobs work_order_notes --all       every approved request with a work order
       python -m app.jobs work_order_notes 42 43       the requests with these ids

It writes to Daftra. Only that one field changes: every other field of the work order is sent back
exactly as Daftra holds it now, since a save empties any field left out, and ملاحظات someone has
already written there are never replaced. Work orders made by hand in Daftra are not touched — only
those a portal request holds. Safe to run again.
"""

import argparse

from sqlalchemy import select

from ..core.database import SessionLocal
from ..modules.invoicing.work_order import add_work_order_notes
from ..modules.models import Request
from .registry import job

# What --all leaves unsaid: nothing to write, or nothing left to write
QUIET = ("no ملاحظات on the request", "already has them")


@job("work_order_notes", label="ملاحظات أوامر الشغل", recorded=False,
     about="Writes the requests' ملاحظات into their work orders' ملاحظات field in Daftra")
def _run(db, who):
    """This one is a command line only: `python -m app.jobs work_order_notes …`."""
    raise SystemExit("Run it as: python -m app.jobs work_order_notes [options]")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", type=int, help="the request ids")
    parser.add_argument("--all", action="store_true", help="every approved request that has a work order")
    parser.add_argument("-n", "--dry-run", action="store_true", help="say what would change, write nothing")
    args = parser.parse_args()
    if bool(args.ids) == args.all:
        parser.error("give request ids or --all, not both and not neither")

    with SessionLocal() as db:
        query = select(Request).order_by(Request.id)
        if args.all:
            query = query.where(Request.status == "approved")
        else:
            query = query.where(Request.id.in_(args.ids))
        requests = db.scalars(query).all()
        for missing in sorted(set(args.ids) - {request.id for request in requests}):
            print(f"  {missing}: no such request")
        done = 0
        for request in requests:
            if request.daftra_work_order_id is None:
                if not args.all:
                    print(f"  {request.id}: no work order in Daftra")
                continue
            result = add_work_order_notes(request, args.dry_run)
            if args.all and result in QUIET:
                continue
            print(f"  {request.id} (أمر شغل {request.daftra_work_order_no}): {result}")
            if result.startswith(("written", "would write")):
                done += 1
    print(f"{done} work order(s) {'to fill' if args.dry_run else 'filled'}")


if __name__ == "__main__":
    main()
