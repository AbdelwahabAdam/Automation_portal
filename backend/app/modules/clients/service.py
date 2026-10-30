"""The portal's customers: finding one, adding an address, and what Daftra says about one.

Daftra stays the source of truth; the portal keeps a copy so a form can find a client by phone
or code at once.
"""

from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.context import Actor
from ...core.errors import NotFound, SyncError
from ...core.text import digits, local_phone
from ...integrations import daftra
from ...integrations.daftra import DaftraError
from ..audit import log as audit_log
from . import in_daftra, repo
from .models import Address, Client


def address_out(address: Address) -> dict:
    return {
        "id": address.id, "emirate": address.emirate, "area": address.area, "street": address.street,
        "house": address.house, "location_url": address.link, "is_default": address.is_default,
    }


def client_match(client: Client) -> dict:
    """A client as the form reads one: the last address on file filled in, and all of them listed."""
    addresses = sorted(client.addresses, key=lambda a: a.id)
    last = addresses[-1] if addresses else None
    return {
        "daftra_id": client.daftra_id, "client_code": client.client_code, "customer_name": client.customer_name,
        "phone": client.phone, "emirate": last.emirate if last else "", "area": last.area if last else "",
        "street": last.street if last else "", "house": last.house if last else "",
        "location_url": last.link if last else "",
        "addresses": [address_out(a) for a in addresses],
    }


def lookup(db: Session, phone: str = "", code: str = "") -> list[Client]:
    """Finds a client in our own copy of Daftra's client list, by phone number or client code."""
    if phone:
        wanted = local_phone(phone)
        return repo.by_phone(db, wanted) if len(wanted) >= repo.MIN_PHONE_DIGITS else []
    wanted = digits(code).zfill(6)
    found = repo.by_code(db, wanted) if wanted.strip("0") else None
    return [found] if found is not None else []


def add_address(db: Session, who: Actor, daftra_id: int, fields: dict) -> tuple[dict, bool, str]:
    """Adds a new address for a client already in our list, e.g. when they have moved.

    It is put on the client in Daftra too, in the one address block Daftra's API can write. If
    that fails the address is still saved here, and the answer says Daftra did not take it, so
    nobody is told it was saved on the client when it was not.
    """
    client = repo.by_daftra_id(db, daftra_id)
    if client is None:
        raise NotFound("العميل غير موجود")
    address = repo.add_address(db, client, {
        "emirate": fields["emirate"].strip(), "area": fields["area"].strip(),
        "street": fields["street"].strip(), "house": fields["house"].strip(),
        "link": fields["location_url"].strip(),
        # Until Daftra has taken it. Marked so the nightly sync keeps it and offers it again.
        "in_daftra": False,
    })
    db.flush()
    out = address_out(address)
    audit_log(db, who, "client.address.add", "client", client.id, client.customer_name, after=out)
    db.commit()

    try:
        in_daftra.save_address(daftra_id, fields)
    except (SyncError, DaftraError) as error:
        return out, False, str(error)
    address.in_daftra = True
    db.commit()
    return out, True, ""


def categories(db: Session) -> list[dict]:
    """Our copy of Daftra's client categories, each with the الإمارة and المنطقة it fills in."""
    return [
        {"id": c.id, "name": c.name, "emirate": c.emirate, "area": c.area}
        for c in repo.categories(db)
    ]


def details_from_daftra(daftra_id: int) -> dict:
    """What a form needs to know about a client from Daftra itself: their current category, where
    Daftra has them, and the invoices that still have something to pay."""
    invoices = in_daftra.open_invoices(daftra_id)
    # Where Daftra has this client: it keeps the point on them, which a map link of theirs
    # often does not — a link shared from a phone holds the place's name and nothing else.
    held = in_daftra.held_custom_fields(daftra_id)
    return {
        "category": daftra.client_category(daftra_id),
        "coordinates": str(held.get(settings.daftra_client_coordinates_field) or "").strip(),
        "open_invoices": [{**invoice, "name": in_daftra.invoice_label(invoice)} for invoice in invoices],
    }
