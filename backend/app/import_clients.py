"""Load clients.json (a Daftra client export) into the local clients and addresses tables.

Usage: python -m app.import_clients [path-to-clients.json]

Only clients with a phone number are kept, since phone is how the sales forms look one up.
Each entry in Daftra's own "addresses" list for a client becomes one row in addresses (most
clients have one; some have several), with the one matching Daftra's "default_address" marked
is_default and given the client's Google Maps "link" (Daftra keeps one link per client, not
per address). Safe to run again: both tables are emptied and rebuilt from the file each time,
matched by Daftra's own client id — this is a straight reflection of the export, not a merge.
"""

import argparse
import json

from .daftra import address_from_daftra, local_phone
from .database import SessionLocal, run_migrations
from .models import Address, Client


def client_rows(path: str) -> tuple[list[dict], int]:
    with open(path, encoding="utf-8-sig") as f:
        raw = json.load(f)["data"]
    rows = []
    for entry in raw:
        c = entry["Client"]
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
        rows.append({
            "daftra_id": int(c["id"]), "client_code": c.get("client_number") or "", "customer_name": name,
            "phone": phone, "phone2": phone2, "email": (c.get("email") or "").strip(),
            "is_active": c.get("suspend") != "1", "addresses": addresses,
        })
    return rows, len(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clients_json", nargs="?", default="../../clients.json")
    args = parser.parse_args()

    rows, total = client_rows(args.clients_json)
    run_migrations()
    with SessionLocal() as db:
        db.query(Address).delete()
        db.query(Client).delete()
        db.add_all(Client(**row) for row in rows)
        db.commit()
    n_addresses = sum(len(row["addresses"]) for row in rows)
    print(f"{len(rows)} of {total} clients kept (had a phone number) and loaded, with {n_addresses} addresses")


if __name__ == "__main__":
    main()
