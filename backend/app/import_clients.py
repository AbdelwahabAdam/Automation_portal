"""Rebuild the local clients and addresses tables from Daftra.

Usage: python -m app.import_clients [path-to-a-client-export.json]

With no argument, fetches every client live from Daftra (app.daftra.list_clients) — this is
what the nightly cron job runs, recorded as a sync run (app.daftra_refresh) like the admin page's button. With a path, reads a Daftra client export instead (the shape
GET /clients.json returns, saved to a file), for offline use or a one-off re-import.

Only clients with a phone number are kept, since phone is how the sales forms look one up.
Each entry in Daftra's own "addresses" list for a client becomes one row in addresses (most
clients have one; some have several), with the one matching Daftra's "default_address" marked
is_default and given the client's Google Maps "link" (Daftra keeps one link per client, not
per address). Safe to run again: both tables are emptied and rebuilt each time, matched by
Daftra's own client id — this is a straight reflection of Daftra, not a merge.
"""

import argparse
import json

from sqlalchemy import select

from .daftra import address_from_daftra
from .text import local_phone
from .database import SessionLocal, run_migrations
from .models import Address, Client


def client_rows(raw_clients: list[dict]) -> list[dict]:
    rows = []
    for c in raw_clients:
        phone, phone2 = local_phone(c.get("phone1")), local_phone(c.get("phone2"))
        if not phone:
            phone, phone2 = phone2, ""
        elif phone2 == phone:
            phone2 = ""
        if not phone:
            continue
        name = (c.get("business_name") or "").strip() or " ".join(
            part for part in ((c.get("first_name") or "").strip(), (c.get("last_name") or "").strip()) if part
        )
        default_id = (c.get("default_address") or {}).get("id", 0)
        entries = c.get("addresses") or [c]
        link = (c.get("link") or "").strip()
        addresses = []
        for a in entries:
            is_default = a.get("id", 0) == default_id
            addresses.append(Address(**address_from_daftra(a), is_default=is_default, link=link if is_default else ""))
        # Daftra's second address block is not one of the "addresses" it lists, so it is taken from
        # the client itself. This is where an address added through the portal lands (daftra_sync.client)
        if str(c.get("active_secondary_address") or "") in ("1", 1):
            second = {key: c.get(f"secondary_{key}") for key in ("address1", "address2", "city", "state")}
            fields = address_from_daftra(second)
            if any(fields.values()) and not any(a.emirate == fields["emirate"] and a.area == fields["area"]
                                                and a.street == fields["street"] and a.house == fields["house"]
                                                for a in addresses):
                addresses.append(Address(**fields, is_default=False, link=""))
        rows.append({
            "daftra_id": int(c["id"]), "client_code": c.get("client_number") or "", "customer_name": name,
            "phone": phone, "phone2": phone2, "email": (c.get("email") or "").strip(),
            "is_active": c.get("suspend") != "1", "addresses": addresses,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clients_json", nargs="?", help="a saved Daftra client export; omit to fetch live from Daftra")
    args = parser.parse_args()

    run_migrations()
    if not args.clients_json:
        # Live from Daftra (the nightly job): recorded as a run, so the admin page shows it
        from .daftra_refresh import run_now
        run = run_now("clients", by_name="المزامنة الليلية")
        if run.status != "done":
            raise SystemExit(f"Client sync failed: {run.error}")
        summary = run.summary
    else:
        with open(args.clients_json, encoding="utf-8-sig") as f:
            raw_clients = [entry["Client"] for entry in json.load(f)["data"]]
        with SessionLocal() as db:
            summary = replace_clients(db, raw_clients)
            db.commit()
    print(f"{summary['kept']} of {summary['daftra_clients']} clients kept (had a phone number) and loaded, "
          f"with {summary['addresses']} addresses")


def replace_clients(db, raw_clients: list[dict]) -> dict:
    """Empties clients and addresses and fills them again from raw_clients, in the caller's
    transaction (the caller commits). Returns counts, and which clients came or went."""
    rows = client_rows(raw_clients)
    before = set(db.scalars(select(Client.daftra_id)))
    db.query(Address).delete()
    db.query(Client).delete()
    db.add_all(Client(**row) for row in rows)
    after = {row["daftra_id"] for row in rows}
    return {
        "daftra_clients": len(raw_clients), "kept": len(rows), "without_phone": len(raw_clients) - len(rows),
        "addresses": sum(len(row["addresses"]) for row in rows),
        "added": len(after - before), "removed": len(before - after),
    }


if __name__ == "__main__":
    main()
