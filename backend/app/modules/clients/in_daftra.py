"""The customer as Daftra holds it: finding one, creating one, and keeping one in step.

This is our knowledge of our own data, not Daftra's API, which is why it does not live in
`integrations/daftra`: the city spellings are the ones our account's clients were typed with,
and the emirate and area are the forms' own choices.
"""

import re
from collections import Counter, defaultdict

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.errors import SyncError
from ...core.text import day_month_year, digits, fold_arabic, local_phone, squash
from ...integrations import daftra
from ...integrations.daftra import DaftraError
from ..form_engine import CUSTOMER_TYPE_CODES, GENDERS
from .models import Address, Client

# Each city as Daftra's clients write it (folded with fold_arabic), as the form's (الإمارة, المنطقة)
CITY_LOCATIONS = {
    fold_arabic(city): location
    for cities, location in [
        (["العين", "alain", "al ain"], ("أبوظبي", "منطقة العين")),
        (["ابو ظبى", "ابوظبى", "ابو ظبي", "أبو ظبي", "أبوظبي", "ابوظبي", "ابو طبى", "ابوطبى", "abu dhabi"],
         ("أبوظبي", "منطقة أبوظبي")),
        (["الظفرة", "الظفره"], ("أبوظبي", "منطقة الظفرة")),
        (["دبى", "دبي", "dubai"], ("دبي", "مدينة دبي")),
        (["حتا", "hatta"], ("دبي", "حتا")),
        (["الشارقه", "الشارقة", "sharjah"], ("الشارقة", "مدينة الشارقة")),
        (["خورفكان", "khorfakkan"], ("الشارقة", "خورفكان")),
        (["كلباء", "kalba"], ("الشارقة", "كلباء")),
        (["عجمان", "ajman"], ("عجمان", "مدينة عجمان")),
        (["ام القوين", "ام القيوين", "أم القيوين", "umm al quwain"], ("أم القيوين", "مدينة أم القيوين")),
        (["راس الخيمه", "رأس الخيمة", "راس الخيمة", "ras al khaimah"], ("رأس الخيمة", "نطاق مدينة رأس الخيمة")),
        (["الفجيره", "الفجيرة", "fujairah"], ("الفجيرة", "مدينة الفجيرة")),
    ]
    for city in cities
}


def city_location(text: str) -> tuple[str, str] | None:
    folded = fold_arabic(re.sub(r"[^\w\s]", " ", (text or "").lower()))
    return CITY_LOCATIONS.get(folded)


def _name_location(name: str) -> tuple[str, str] | None:
    """A category whose name holds its city, e.g. «دبي البرشاء 3» or «الزعفرانه ابو ظبى»."""
    words = (name or "").split()
    for size in (2, 1):
        for start in range(len(words) - size + 1):
            found = city_location(" ".join(words[start:start + size]))
            if found:
                return found
    return None


def address_from_daftra(client: dict) -> dict:
    """A Daftra client (or one of its addresses) as our address fields.

    The emirate comes from CITY_LOCATIONS, which knows the spellings Daftra's data uses for the
    same place — «دبى», «دبي», «Dubai» — and the cities that are not emirates (العين, حتا).
    The area keeps the neighbourhood Daftra holds («الخوانيج 2»), which is what the installation
    team needs on the work order; it is not one of the regions the form lists.
    """
    city, area = (client.get("city") or "").strip(), (client.get("state") or "").strip()
    found = city_location(city)
    if found:
        # With no neighbourhood of its own, the city's own region says where it is («العين» is
        # not أبوظبي the city), and that one the form does offer
        emirate, area = found[0], area or found[1]
    elif city_location(area):
        # The two are the other way round on some clients: «السمحه» as the city, «ابو ظبي» as the area
        emirate, area = city_location(area)[0], city
    else:
        # Keep an unrecognised city visible in the area instead of dropping it
        emirate = ""
        area = "، ".join(part for part in (city, area) if part)
    return {
        "emirate": emirate,
        "area": area,
        "street": (client.get("address1") or "").strip(),
        "house": (client.get("address2") or "").strip(),
    }


CATEGORY_LOCATIONS = "client_categories_with_location"


def categories_with_location() -> list[dict]:
    """The client categories, each with the الإمارة and المنطقة so picking one can fill both in:
    where its clients mostly live, else the city in its name, else that of the other categories
    starting with the same word (e.g. «الشامخه 1» like «الشامخه»); None where nothing tells.
    It reads every client (over a minute), so it is kept for hours and warmed at startup."""
    def load():
        votes: dict[int, Counter] = defaultdict(Counter)
        for client in daftra.all_records("clients", "Client", workers=8):
            location = city_location(client.get("city") or "")
            if client.get("category_id") and location:
                votes[int(client["category_id"])][location] += 1
        categories = daftra.list_client_categories()
        found = {}
        for category in categories:
            counted = votes.get(category["id"])
            found[category["id"]] = counted.most_common(1)[0][0] if counted else _name_location(category["name"])
        by_first_word: dict[str, Counter] = defaultdict(Counter)
        for category in categories:
            if found[category["id"]] and category["name"].split():
                by_first_word[fold_arabic(category["name"].split()[0])][found[category["id"]]] += 1
        rows = []
        for category in categories:
            location = found[category["id"]]
            if location is None and category["name"].split():
                same = by_first_word.get(fold_arabic(category["name"].split()[0]))
                location = same.most_common(1)[0][0] if same else None
            rows.append({**category, "emirate": location[0] if location else None,
                         "area": location[1] if location else None})
        return rows

    return daftra.cached(CATEGORY_LOCATIONS, load, seconds=6 * 60 * 60)


def open_invoices(client_id: int) -> list[dict]:
    """The client's issued invoices that still have something to pay, newest first."""
    found = []
    for row in daftra.client_invoices(client_id):
        invoice = row["Invoice"]
        unpaid = float(invoice.get("summary_unpaid") or 0)
        if invoice.get("draft") == "0" and unpaid > 0.005:
            # The list gives 2026-10-19; Daftra prints 19/10/2026
            day = day_month_year(invoice.get("date") or "")
            found.append({"id": int(invoice["id"]), "no": invoice.get("no") or "", "date": day,
                          "total": float(invoice.get("summary_total") or 0), "unpaid": round(unpaid, 2)})
    return sorted(found, key=lambda invoice: invoice["id"], reverse=True)


def invoice_label(invoice: dict) -> str:
    """How an open invoice reads in the balance-payment form, e.g. «06273 — 18/10/2026 — المتبقي 4,650 درهم»."""
    return f"{invoice['no']} — {invoice['date']} — المتبقي {invoice['unpaid']:,.2f}".removesuffix(".00") + " درهم"


# ---------- The address, as Daftra keeps one ----------


def address_fields(data: dict) -> dict:
    """An address as Daftra keeps one: the city holds the emirate and the state holds the area
    (daftra.address_from_daftra reads them back that way). It goes on the client, and on the
    invoice, where it is the address printed for that request."""
    return {"address1": str(data.get("street") or "").strip(), "address2": str(data.get("house") or "").strip(),
            "city": str(data.get("emirate") or "").strip(), "state": str(data.get("area") or "").strip(),
            "country_code": "AE"}


# ---------- Finding, creating and keeping a client in step ----------


def client_id(data: dict, db: Session) -> int:
    """The Daftra client this request is for: an existing one, else a new one."""
    found = existing_client_id(data, db)
    return found if found is not None else create_client(data, local_phone(data.get("phone")), db)


def known_client(data: dict, db: Session) -> bool:
    """Whether our client list has a client with the request's client code or phone: the same list
    the form's phone search reads, so the form and the server agree on who is a new client."""
    code = digits(data.get("client_code"))
    if code.strip("0") and db.scalar(select(Client.id).where(Client.client_code == code.zfill(6)).limit(1)):
        return True
    phone = local_phone(data.get("phone"))
    return len(phone) >= 9 and db.scalar(
        select(Client.id).where(or_(Client.phone == phone, Client.phone2 == phone)).limit(1)) is not None


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
    # Daftra keeps the city in "city" and the area in "state" (address_from_daftra above reads them back)
    body = {
        "Client": {
            "business_name": name, "phone1": phone,
            # نوع العميل and الجنس as Daftra's codes (forms.options). Neither is required: one left
            # empty gets what every client got before the form asked: an individual, gender not set
            "type": CUSTOMER_TYPE_CODES.get(data.get("customer_type"), 2),
            **({"gender": GENDERS[data["gender"]]} if data.get("gender") in GENDERS else {}),
            **({"email": data["email"]} if data.get("email") else {}),
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
        email=data.get("email") or "",
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


def update_client(daftra_client_id: int, data: dict):
    """Puts on the client in Daftra what a request knows about them: the التصنيف picked on the
    form, the رابط اللوكيشن and the الإحداثيات of the address it is for.

    It takes the id and the request's data rather than the request itself, so `clients` needs to
    know nothing about `requests` — the two would otherwise import each other.

    Daftra is only written to when something would actually change, and the newest request wins:
    a client has one link and one pair of coordinates, so they follow the address last used.
    """
    resource = f"clients/{daftra_client_id}.json"
    saved = daftra.get(resource).get("data", {}).get("Client", {})
    held = held_custom_fields(daftra_client_id)
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
