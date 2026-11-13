"""Does Daftra email an invoice the API creates with «send by email» left on?

A one-off probe, run by hand on the server against the LIVE account. It is not wired into the
portal and nothing imports it: it answers one question and is then thrown away.

What it is for
--------------
Every invoice the portal creates carries `is_offline: 1` — «do not email this, it is printed and
handed over» — so Daftra never asks for the client's email. عرض سعر was missing that flag, which
is why Daftra refused to save one for a client with no email address.

The code says Daftra's own «send to client» works only for someone logged in to Daftra, never
through the API (modules/invoicing/client_email.py). If that is right, dropping the flag makes
Daftra *demand* an address and still send nothing. This finds out.

Usage, inside the backend container on the server:

    python email_invoice_probe.py 4053            # read only: the client, its email, the payload
    python email_invoice_probe.py 4053 --create   # actually create the invoice in the live account

Without --create nothing is written. With it, ONE invoice is created, final (not a draft), for
one line of 1 AED, marked «PORTAL-EMAILTEST» in its PO number and said so in its notes.

It posts to the live accounts, so delete it in Daftra when the question is answered.
"""

import argparse
import json
import sys

from app.core.config import settings
from app.integrations import daftra

# What the invoice is marked with, so it is obvious in the list and easy to find again
MARKER = "PORTAL-EMAILTEST"
NOTE = "فاتورة اختبار من البوابة — للتحقق من إرسال البريد. يمكن حذفها."


def read_client(client_id: int) -> dict:
    found = daftra.get(f"clients/{client_id}.json").get("data", {}).get("Client", {})
    if not found:
        raise SystemExit(f"Daftra has no client {client_id}")
    return found


def invoice_body(client_id: int, date: str) -> dict:
    """The portal's own invoice payload, minus `is_offline` — that is the whole experiment.

    Everything else is kept exactly as `modules/invoicing/invoice.py` sends it, so the only
    difference between this and a real approval is the flag under test.
    """
    return {
        "Invoice": {
            "client_id": client_id,
            "date": date,
            "draft": 0,
            # is_offline is deliberately absent: the account's own setting applies, which is the
            # «يرسل بالبريد» that made Daftra ask for client_email on عرض سعر
            "currency_code": "AED",
            "store_id": settings.daftra_store_id,
            "branch_id": settings.daftra_branch_id,
            "po_number": MARKER,
            "notes": NOTE,
        },
        "InvoiceItem": [{
            "item": "Portal email test",
            "description": NOTE,
            "unit_price": 1.0,
            "quantity": 1,
            "tax1": settings.daftra_tax_id,
            "store_id": settings.daftra_store_id,
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("client_id", type=int, help="the Daftra client id, e.g. 4053")
    parser.add_argument("--create", action="store_true", help="actually create it (writes to Daftra)")
    parser.add_argument("--date", default="", help="the invoice date (default: today in the UAE)")
    args = parser.parse_args()

    if settings.daftra_fake:
        raise SystemExit("DAFTRA_FAKE is on. This probe is only worth running against the live account.")
    print(f"Account: {settings.daftra_subdomain}.daftra.com\n")

    client = read_client(args.client_id)
    name = client.get("business_name") or f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
    email = str(client.get("email") or "").strip()
    print(f"Client {args.client_id}: «{name}»")
    print(f"  client_number : {client.get('client_number') or '—'}")
    print(f"  phone1        : {client.get('phone1') or '—'}")
    print(f"  email         : {email or '— (none on the record)'}")
    if not email:
        print("\nNo email on the client. Daftra will refuse to save an invoice it is meant to send:")
        print('  {"client_email": "البريد الإلكتروني مطلوب إذا اخترت أن ترسل الفاتورة عبر البريد"}')
        print("That alone answers half the question. Put an address on the client in Daftra to go further.")

    from app.core.text import uae_today
    body = invoice_body(args.client_id, args.date or uae_today().isoformat())
    print("\nWhat would be sent to POST /api2/invoices.json:")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    if not args.create:
        print("\nNothing was written. Add --create to actually make it.")
        return 0

    print("\nCreating it…")
    try:
        invoice_id = daftra.create("invoices.json", body)
    except daftra.DaftraError as error:
        print(f"\nDaftra REFUSED it:\n  {error}")
        print("\nSo the flag is a gate, not a send button: without is_offline Daftra insists on an\n"
              "address before it will save. Keep is_offline on every document the portal creates.")
        return 1

    print(f"  created invoice {invoice_id}")
    saved = daftra.get(f"invoices/{invoice_id}.json").get("data", {}).get("Invoice", {})
    print(f"  number        : {saved.get('no')}")
    print(f"  is_offline    : {saved.get('is_offline')!r}")
    print(f"  client_email  : {saved.get('client_email')!r}")
    print(f"  sent / emailed: {saved.get('sent')!r} / {saved.get('email_sent')!r}")
    print(f"  open it       : https://{settings.daftra_subdomain}.daftra.com/owner/invoices/view/{invoice_id}")
    print("\nNow check the client's inbox.")
    print("  • an email arrives  -> Daftra does send through the API, and emailing from the portal is a choice")
    print("  • nothing arrives   -> the note in client_email.py still holds: only a logged-in user can send it")
    print(f"\nThis invoice is in the live accounts. Delete it in Daftra when you are done ({MARKER}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
