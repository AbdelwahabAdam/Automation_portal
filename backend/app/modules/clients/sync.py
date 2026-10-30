"""Bringing our copy of Daftra's client list up to date.

Daftra is the source of truth, so this is a reflection of it, not a merge — with one exception.
An address saved in the portal that Daftra refused (`in_daftra` false) is kept and offered to
Daftra again at the start of the next sync; it used to be wiped that night, because the sync
emptied both tables and built them again.

Keyed on Daftra's own client id, so a client and its addresses keep their row — and their id —
from one night to the next.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...core.text import local_phone
from . import in_daftra as daftra_side
from .models import Address, Client

# What identifies an address, so one already on file is recognised rather than replaced
ADDRESS_KEY = ("emirate", "area", "street", "house")


def client_rows(raw_clients: list[dict]) -> list[dict]:
    """Daftra's clients as our rows, each with its addresses as plain field dicts.

    Only clients with a phone number are kept, since phone is how the forms look one up.
    """
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
            addresses.append({**daftra_side.address_from_daftra(a), "is_default": is_default,
                              "link": link if is_default else ""})
        # Daftra's second address block is not one of the "addresses" it lists, so it is taken from
        # the client itself. This is where an address added through the portal lands.
        if str(c.get("active_secondary_address") or "") in ("1", 1):
            second = {key: c.get(f"secondary_{key}") for key in ("address1", "address2", "city", "state")}
            fields = daftra_side.address_from_daftra(second)
            if any(fields.values()) and not any(
                all(a[key] == fields[key] for key in ADDRESS_KEY) for a in addresses
            ):
                addresses.append({**fields, "is_default": False, "link": ""})
        rows.append({
            "daftra_id": int(c["id"]), "client_code": c.get("client_number") or "", "customer_name": name,
            "phone": phone, "phone2": phone2, "email": (c.get("email") or "").strip(),
            "is_active": c.get("suspend") != "1", "addresses": addresses,
        })
    return rows


def _key(fields) -> tuple:
    if isinstance(fields, dict):
        return tuple(fields[name] for name in ADDRESS_KEY)
    return tuple(getattr(fields, name) for name in ADDRESS_KEY)


def resend_held_addresses(db: Session) -> dict:
    """Offers Daftra again every address it has not taken. Run before reading its clients back,
    so one it accepts now comes back with them instead of looking like ours alone."""
    held = list(db.scalars(
        select(Address).where(Address.in_daftra.is_(False)).options(selectinload(Address.client))
    ))
    accepted, refused = 0, 0
    for address in held:
        client = address.client
        if client is None:
            continue
        try:
            daftra_side.save_address(client.daftra_id, {
                "emirate": address.emirate, "area": address.area, "street": address.street,
                "house": address.house, "location_url": address.link, "coordinates": "",
            })
        except Exception:                           # noqa: BLE001 — any refusal keeps it for next time
            refused += 1
            continue
        address.in_daftra = True
        accepted += 1
    if held:
        db.commit()
    return {"resent": len(held), "accepted": accepted, "still_refused": refused}


def _apply_addresses(client: Client, wanted: list[dict]) -> int:
    """Makes the client carry exactly these addresses, keeping the rows it already has.

    An address the portal saved and Daftra has not taken is left alone — it is not Daftra's to
    remove, and the next sync offers it again.
    """
    ours = [a for a in client.addresses if not a.in_daftra]
    from_daftra = {_key(a): a for a in client.addresses if a.in_daftra}
    kept = []
    for fields in wanted:
        existing = from_daftra.pop(_key(fields), None)
        if existing is None:
            existing = Address(**{name: fields[name] for name in ADDRESS_KEY}, in_daftra=True)
        existing.is_default = fields["is_default"]
        existing.link = fields["link"]
        kept.append(existing)
    client.addresses = kept + ours
    return len(kept)


def sync_from_daftra(db: Session, raw_clients: list[dict]) -> dict:
    """Brings clients and addresses in step with Daftra's list, in the caller's transaction."""
    rows = client_rows(raw_clients)
    existing = {c.daftra_id: c for c in db.scalars(select(Client).options(selectinload(Client.addresses)))}
    seen, addresses = set(), 0
    added = updated = 0
    for row in rows:
        fields = {key: value for key, value in row.items() if key != "addresses"}
        client = existing.get(row["daftra_id"])
        if client is None:
            client = Client(**fields)
            db.add(client)
            added += 1
        else:
            changed = any(getattr(client, name) != value for name, value in fields.items())
            for name, value in fields.items():
                setattr(client, name, value)
            updated += changed
        db.flush()
        addresses += _apply_addresses(client, row["addresses"])
        seen.add(row["daftra_id"])

    gone = [client for daftra_id, client in existing.items() if daftra_id not in seen]
    for client in gone:
        db.delete(client)
    return {
        "daftra_clients": len(raw_clients), "kept": len(rows), "without_phone": len(raw_clients) - len(rows),
        "addresses": addresses, "added": added, "updated": updated, "removed": len(gone),
    }
