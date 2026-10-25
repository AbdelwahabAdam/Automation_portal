"""The Daftra client a request is for: found by client code or phone, or created."""

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import daftra
from ..config import settings
from ..daftra import DaftraError, local_phone
from ..models import Address, Client, Request
from ..text import digits, squash
from .common import SyncError, address_fields


def client_id(data: dict, db: Session) -> int:
    """The Daftra client this request is for: an existing one, else a new one."""
    found = existing_client_id(data, db)
    return found if found is not None else create_client(data, local_phone(data.get("phone")), db)


def existing_client_id(data: dict, db: Session) -> int | None:
    """The Daftra client with the request's client code, else its phone number; None if there is none."""
    code = digits(data.get("client_code"))
    if code.strip("0"):
        client = db.scalar(select(Client).where(Client.client_code == code.zfill(6)))
        if client is not None:
            return client.daftra_id

    phone = local_phone(data.get("phone"))
    if len(phone) < 9:
        return None
    known = db.scalars(select(Client).where(or_(Client.phone == phone, Client.phone2 == phone))).all()
    if len(known) > 1:
        raise SyncError(f"يوجد أكثر من عميل بالرقم {phone} ولم يُحدَّد كود العميل. "
                        "أعد الطلب للموظف ليكتب كود العميل الصحيح.")
    if known:
        return known[0].daftra_id

    # Our copy of the client list may be older than Daftra's
    rows = daftra.get("clients.json", {"keywords": phone, "limit": 50}).get("data", [])
    found = [row["Client"] for row in rows
             if phone in (local_phone(row["Client"].get("phone1")), local_phone(row["Client"].get("phone2")))]
    if len(found) > 1:
        raise SyncError(f"يوجد في دفترة أكثر من عميل بالرقم {phone}. أعد الطلب للموظف ليكتب كود العميل الصحيح.")
    return int(found[0]["id"]) if found else None


def custom_fields(data: dict, held: dict | None = None) -> dict:
    """The two fields our Daftra account demands on any client it saves: اسم الجهاز and Coordinates.
    An empty one is refused with «هذا الحقل مطلوب», whether the client is being created or changed.

    held: what the client already has in those fields, used for whatever the request does not say.
    A request's own الإحداثيات win, which is how a client's location follows them when they move.
    """
    held = held or {}
    # اسم الجهاز is not asked on the form any more; a request from before keeps the one typed then
    device = (str(data.get("device_name") or "").strip()
              or str(held.get(settings.daftra_client_device_field) or "").strip()
              or settings.daftra_default_device_name)
    coordinates = (str(data.get("coordinates") or "").strip()
                   or str(held.get(settings.daftra_client_coordinates_field) or "").strip())
    if not coordinates:
        # Requests submitted before the form asked for them, for a client that has none either
        raise SyncError("دفترة تتطلب «الإحداثيات» للعميل، وهي غير موجودة في الطلب. "
                        "أعد الطلب للموظف ليكملها، ثم اعتمده بعد إعادة الإرسال.")
    return {
        settings.daftra_client_device_field: device,
        settings.daftra_client_coordinates_field: coordinates,
    }


def usable_link(data: dict) -> str:
    """The request's رابط اللوكيشن, if Daftra will have it: it keeps the link on the client and
    checks it is one, in 255 characters. A request from before the form asked for a real link may
    hold anything — coordinates typed into the wrong box — and that is no reason to refuse the
    whole approval: the الإحداثيات go to Daftra either way, and the link stays in the portal.
    """
    link = str(data.get("location_url") or "").strip()
    return link if re.match(r"^https?://\S+$", link) and len(link) <= 255 else ""


def address_change(saved: dict, address: dict) -> dict:
    """What to send so the client in Daftra carries this address, or nothing when it already does.

    Daftra's API can write two addresses on a client: its own, and one «secondary» block. The
    others a client may have exist only in Daftra's own screens, with no API behind them. So an
    address goes into the client's own block while that is empty, and after that into the
    secondary one, where the newest address the portal is told about takes the slot.
    """
    filled = ("address1", "address2", "state", "city")
    if not any(address[key] for key in ("address1", "address2", "state")):
        return {}
    own = {key: str(saved.get(key) or "").strip() for key in address}
    if own == address:
        return {}  # Daftra has it as the client's own address
    if not any(own[key] for key in filled):
        return dict(address)  # the client has no address of its own, so it goes there
    second = {key: str(saved.get(f"secondary_{key}") or "").strip() for key in address}
    if second == address and str(saved.get("active_secondary_address") or "") in ("1", 1, "true", "True"):
        return {}
    return {"active_secondary_address": 1, **{f"secondary_{key}": value for key, value in address.items()}}


def held_custom_fields(client_id: int) -> dict:
    """What the client's required custom fields hold now. Only the read API v2 returns them, and
    only it: the client itself comes back without them, however it is asked for."""
    try:
        return daftra.read_v2("client", client_id).get("client_custom_data") or {}
    except DaftraError:
        return {}


def create_client(data: dict, phone: str, db: Session) -> int:
    name = squash(data.get("customer_name"))
    fields = custom_fields(data)
    # Daftra keeps the city in "city" and the area in "state" (see daftra.address_from_daftra, which reads them back)
    body = {
        "Client": {
            "business_name": name, "type": 2, "phone1": phone,
            "address1": data.get("street") or "", "address2": data.get("house") or "",
            "city": data.get("emirate") or "", "state": data.get("area") or "",
            "country_code": "AE", "default_currency_code": "AED",
            **({"category_id": data["category"], "category": data.get("category_name") or ""} if data.get("category") else {}),
        },
        # The account's required client custom fields
        "le_custom_data_client": fields,
    }
    new_id = daftra.create("clients.json", body, {"skip_email": 1})
    row = daftra.get(f"clients/{new_id}.json").get("data", {}).get("Client", {})
    db.add(Client(
        daftra_id=new_id, client_code=str(row.get("client_number") or new_id)[:10], customer_name=name, phone=phone,
        addresses=[Address(emirate=data.get("emirate") or "", area=data.get("area") or "", street=data.get("street") or "",
                           house=data.get("house") or "", link=data.get("location_url") or "", is_default=True)],
    ))
    return new_id


def save_address(daftra_id: int, data: dict):
    """Puts an address the salesperson has just saved on the client in Daftra, with its location
    link. Raises SyncError, so the salesperson is told rather than left thinking Daftra has it.
    """
    resource = f"clients/{daftra_id}.json"
    saved = daftra.get(resource).get("data", {}).get("Client", {})
    wanted = address_change(saved, address_fields(data))
    link = usable_link(data)
    if link and str(saved.get("link") or "").strip() != link:
        wanted["link"] = link
    if not wanted:
        return
    custom = custom_fields(data, held_custom_fields(daftra_id))
    client = {**wanted, "business_name": saved.get("business_name") or "",
              "first_name": saved.get("first_name") or "", "last_name": saved.get("last_name") or ""}
    daftra.update(resource, {"Client": client, "le_custom_data_client": custom})


def update_client(request: Request):
    """Puts on the client in Daftra what this request knows about them: the التصنيف picked on the
    form, the رابط اللوكيشن and the الإحداثيات of the address it is for.

    Daftra is only written to when something would actually change, and the newest request wins:
    a client has one link and one pair of coordinates, so they follow the address last used.
    """
    data = request.data
    resource = f"clients/{request.daftra_client_id}.json"
    saved = daftra.get(resource).get("data", {}).get("Client", {})
    held = held_custom_fields(request.daftra_client_id)
    wanted, custom = {}, custom_fields(data, held)

    if data.get("category") and str(saved.get("category_id") or "") != str(data["category"]):
        wanted["category_id"] = data["category"]
        wanted["category"] = data.get("category_name") or ""
    link = usable_link(data)
    if link and str(saved.get("link") or "").strip() != link:
        wanted["link"] = link
    wanted.update(address_change(saved, address_fields(data)))
    # The coordinates live in a custom field, which is saved separately from the client's own fields
    if custom == {key: str(held.get(key) or "") for key in custom} and not wanted:
        return

    # Daftra rebuilds the client's name out of the name fields of whatever is sent to it: left out
    # of the body, business_name becomes the empty first and last name joined by a space. So the
    # name the client already has goes back with the change, unchanged.
    client = {**wanted, "business_name": saved.get("business_name") or "",
              "first_name": saved.get("first_name") or "", "last_name": saved.get("last_name") or ""}
    # The account refuses any client save that does not carry those two fields, so they always go
    daftra.update(resource, {"Client": client, "le_custom_data_client": custom})
