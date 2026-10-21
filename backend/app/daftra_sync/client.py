"""The Daftra client a request is for: found by client code or phone, or created."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import daftra
from ..config import settings
from ..daftra import DaftraError, local_phone
from ..models import Address, Client, Request
from ..text import digits, squash
from .common import SyncError


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


def custom_fields(data: dict) -> dict:
    """The two fields our Daftra account demands on any client it saves: اسم الجهاز and Coordinates.
    An empty one is refused with «هذا الحقل مطلوب», whether the client is being created or changed."""
    # اسم الجهاز is not asked on the form any more; a request from before keeps the one typed then
    device = str(data.get("device_name") or "").strip() or settings.daftra_default_device_name
    coordinates = str(data.get("coordinates") or "").strip()
    if not coordinates:
        # Requests submitted before the form asked for them
        raise SyncError("دفترة تتطلب «الإحداثيات» للعميل، وهي غير موجودة في الطلب. "
                        "أعد الطلب للموظف ليكملها، ثم اعتمده بعد إعادة الإرسال.")
    return {
        settings.daftra_client_device_field: device,
        settings.daftra_client_coordinates_field: coordinates,
    }


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


def set_client_category(request: Request):
    """Gives the request's client the التصنيف picked on the form.

    Daftra is only written to when the category would actually change. When it is written to, it
    checks the client's required custom fields; for a client whose fields are empty (one added
    before they existed, or outside the portal) the save is refused, so it is sent again with them.
    """
    data = request.data
    if not data.get("category"):
        return
    resource = f"clients/{request.daftra_client_id}.json"
    saved = daftra.get(resource).get("data", {}).get("Client", {})
    if str(saved.get("category_id") or "") == str(data["category"]):
        return

    # Daftra rebuilds the client's name out of the name fields of whatever is sent to it: left out
    # of the body, business_name becomes the empty first and last name joined by a space. So the
    # name the client already has goes back with the category, unchanged.
    client = {"category_id": data["category"], "category": data.get("category_name") or "",
              "business_name": saved.get("business_name") or "",
              "first_name": saved.get("first_name") or "", "last_name": saved.get("last_name") or ""}
    try:
        # On its own first, so a client that already has those fields keeps what is in them
        daftra.update(resource, {"Client": client})
    except DaftraError:
        daftra.update(resource, {"Client": client, "le_custom_data_client": custom_fields(data)})
