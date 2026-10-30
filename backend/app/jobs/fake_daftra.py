"""The fake Daftra account's commands, and the seed that fills it from the local database.

    python -m app.fake_daftra calls                                  the last 20 calls
    python -m app.fake_daftra fail-once /api2/invoice_payments.json  that call fails once
    python -m app.fake_daftra seed                                   add what the database has gained
    python -m app.fake_daftra reset                                  forget everything

They refuse unless DAFTRA_FAKE is on. The seed reads the database, which is why it lives here
and not in `integrations/`: the Daftra client imports no module of ours, and is handed plain data.

Phase 5 moves these under `python -m app.jobs fake_daftra …`.
"""

import json
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..core.database import SessionLocal
from ..integrations.daftra import fake
from ..modules.models import Client, ClientCategory, Product, User
from .registry import job

# How many of the kept calls `calls` prints
SHOWN_CALLS = 20


def _seed_data(db) -> dict:
    """What the local database knows, as the plain data the fake takes.

    Without this, approving a request for an existing client fails: the fake has never seen
    that client's Daftra id, so the save it tries answers 404.
    """
    clients = []
    for client in db.scalars(select(Client).options(selectinload(Client.addresses))):
        first = next((a for a in client.addresses if a.is_default), None) or next(iter(client.addresses), None)
        clients.append({
            "daftra_id": client.daftra_id,
            "client_code": client.client_code,
            "name": client.customer_name,
            "phone": client.phone,
            "phone2": client.phone2 or "",
            "link": first.link if first else "",
            # Daftra keeps the emirate in "city" and the area in "state"
            "address": {"city": first.emirate, "state": first.area,
                        "address1": first.street, "address2": first.house} if first else {},
        })
    products = [{"daftra_id": product.daftra_id, "name": product.name, "unit_price": str(product.unit_price)}
                for product in db.scalars(select(Product).where(Product.daftra_id.is_not(None)))]
    categories = [{"daftra_id": category.id, "name": category.name}
                  for category in db.scalars(select(ClientCategory))]
    staff = [{"daftra_staff_id": user.daftra_staff_id, "name": user.full_name or user.username}
             for user in db.scalars(select(User).where(User.daftra_staff_id.is_not(None)))]
    return {"clients": clients, "products": products, "categories": categories, "staff": staff}


def seed() -> dict:
    """Adds to the fake what the local database has that it has not seen. Safe to run again."""
    with SessionLocal() as db:
        return fake.account().seed(_seed_data(db))



@job("fake_daftra", label="دفترة التجريبية", recorded=False,
     about="The fake Daftra account's own commands")
def _run(db, who):
    """This one is a command line only: `python -m app.jobs fake_daftra …`."""
    raise SystemExit("Run it as: python -m app.jobs fake_daftra [options]")

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not settings.daftra_fake:
        print("DAFTRA_FAKE is off: these commands are only for the fake Daftra account.", file=sys.stderr)
        return 2
    command = argv[0] if argv else "calls"
    account = fake.account()

    if command == "calls":
        for method, path, params, body in account.calls[-SHOWN_CALLS:]:
            print(f"{method} {path}")
            if params:
                print(f"    params {json.dumps(params, ensure_ascii=False)}")
            if body is not None:
                print(f"    body   {json.dumps(body, ensure_ascii=False, default=str)}")
        if not account.calls:
            print("No calls yet.")
    elif command == "fail-once":
        if len(argv) < 2:
            print("fail-once needs the call to fail, e.g. /api2/invoice_payments.json", file=sys.stderr)
            return 2
        account.fail_once = argv[1]
        account.save()
        print(f"The next call to {argv[1]} will fail once.")
    elif command == "seed":
        added = seed()
        print("Added: " + ", ".join(f"{count} {name}" for name, count in added.items()))
    elif command == "reset":
        account.reset()
        fake.use(None)
        print("The fake Daftra account is empty; the next start seeds it again.")
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
