"""Bringing our copy of Daftra's client list up to date.

    python -m app.jobs sync_clients                     live from Daftra (what cron runs)
    python -m app.jobs sync_clients <clients.json>       from a saved Daftra export instead

Runs nightly from cron and from the «المزامنة مع دفترة» page. The rules live in
`modules/clients`; this only runs them.
"""

import argparse
import json

from ..core.database import SessionLocal, run_migrations
from ..integrations import daftra
from ..modules import clients
from .registry import job


@job("sync_clients", label="العملاء", on_admin_page=True,
     about="Brings clients and addresses in step with Daftra")
def sync_clients(db, who) -> dict:
    # An address Daftra has not taken is offered again first, so one it accepts now comes back
    # with the clients instead of looking like ours alone
    held = clients.resend_held_addresses(db)
    summary = clients.sync_from_daftra(db, daftra.list_clients())
    return {**summary, **({"held_addresses": held} if held["resent"] else {})}


def main(argv: list[str] | None = None) -> int:
    """The command line. With a path it reads a saved Daftra export (the shape
    GET /clients.json returns), for offline use or a one-off re-import; without one it runs the
    job itself, recorded like the admin page's button."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clients_json", nargs="?",
                        help="a saved Daftra client export; omit to fetch live from Daftra")
    args = parser.parse_args(argv)

    run_migrations()
    if not args.clients_json:
        from .runner import run_now

        run = run_now("sync_clients")
        if run.status != "done":
            raise SystemExit(f"Client sync failed: {run.error}")
        summary = run.summary
    else:
        with open(args.clients_json, encoding="utf-8-sig") as handle:
            raw_clients = [entry["Client"] for entry in json.load(handle)["data"]]
        with SessionLocal() as db:
            summary = clients.sync_from_daftra(db, raw_clients)
            db.commit()
    print(f"{summary['kept']} of {summary['daftra_clients']} clients kept (had a phone number) and loaded, "
          f"with {summary['addresses']} addresses")
    return 0
