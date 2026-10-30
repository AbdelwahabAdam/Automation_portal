"""What the sales forms look things up in: our copy of Daftra's clients, our catalog, and Daftra's
own lists (staff, treasuries, order sources, a client's open invoices)."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from . import catalog, daftra, daftra_sync, location
from .audit import Audit
from .config import settings
from .text import local_phone
from .database import get_db
from .models import Address, Client, ClientCategory, Package, PackageItem, Product, User
from .security import sales_user
from .text import digits

router = APIRouter(prefix="/api")


# ---------- Clients ----------

def address_out(address: Address) -> dict:
    return {
        "id": address.id, "emirate": address.emirate, "area": address.area, "street": address.street,
        "house": address.house, "location_url": address.link, "is_default": address.is_default,
    }


def client_match(client: Client) -> dict:
    addresses = sorted(client.addresses, key=lambda a: a.id)
    last = addresses[-1] if addresses else None
    return {
        "daftra_id": client.daftra_id, "client_code": client.client_code, "customer_name": client.customer_name,
        "phone": client.phone, "emirate": last.emirate if last else "", "area": last.area if last else "",
        "street": last.street if last else "", "house": last.house if last else "",
        "location_url": last.link if last else "",
        "addresses": [address_out(a) for a in addresses],
    }


@router.get("/location/from-link")
def point_of_link(url: str, user: User = Depends(sales_user)):
    """Where a map link points, so pasting one moves the pin. The browser cannot follow a short
    link itself — reading another site's redirect is not allowed — so it is followed here."""
    try:
        lat, lng = location.resolve(url)
    except location.NotALocation as why:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(why)) from why
    return {"lat": lat, "lng": lng}


@router.get("/clients/lookup")
def lookup_client(phone: str = "", code: str = "", user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Finds a client in our own copy of Daftra's client list, by phone number or client code.

    The address filled in is the last one on file for that client; "addresses" lists all of
    them, so the sales form can offer a different one or let the user add a new one.
    """
    query = select(Client).options(selectinload(Client.addresses))
    if phone:
        wanted = local_phone(phone)
        matches = [] if len(wanted) < 9 else db.scalars(
            query.where(or_(Client.phone == wanted, Client.phone2 == wanted))
        ).all()
    else:
        wanted = digits(code).zfill(6)
        matches = [] if not wanted.strip("0") else db.scalars(query.where(Client.client_code == wanted)).all()
    return {"matches": [client_match(c) for c in matches]}


class AddressIn(BaseModel):
    emirate: str = Field("", max_length=50)
    area: str = Field("", max_length=100)
    street: str = Field("", max_length=200)
    house: str = Field("", max_length=100)
    location_url: str = Field("", max_length=600)
    coordinates: str = Field("", max_length=100)


@router.post("/clients/{daftra_id}/addresses")
def add_client_address(daftra_id: int, body: AddressIn, user: User = Depends(sales_user),
                       db: Session = Depends(get_db), audit: Audit = Depends()):
    """Adds a new address for a client already in our list, e.g. when they have moved.

    It is put on the client in Daftra too, in the one address block Daftra's API can write. If
    that fails the address is still saved here, and the answer says Daftra did not take it, so
    nobody is told it was saved on the client when it was not.
    """
    client = db.scalar(select(Client).where(Client.daftra_id == daftra_id))
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "العميل غير موجود")
    address = Address(client_id=client.id, emirate=body.emirate.strip(), area=body.area.strip(),
                      street=body.street.strip(), house=body.house.strip(), link=body.location_url.strip())
    db.add(address)
    db.flush()
    audit.log(user, "client.address.add", "client", client.id, client.customer_name, after=address_out(address))
    db.commit()

    saved_in_daftra, problem = True, ""
    try:
        daftra_sync.save_address(daftra_id, body.model_dump())
    except (daftra_sync.SyncError, daftra.DaftraError) as error:
        saved_in_daftra, problem = False, str(error)
    return {**address_out(address), "saved_in_daftra": saved_in_daftra, "daftra_error": problem}


# ---------- Our catalog ----------

def price_or_none(value) -> float | None:
    return float(value) if value else None


@router.get("/products")
def products_for_sales(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Our own catalog, for the product field's search box (not Daftra's, which carries duplicate names)."""
    rows = db.scalars(select(Product).where(Product.is_active).order_by(func.lower(Product.name))).all()
    return [
        {"id": row.id, "name": row.name, "name_ar": row.name_ar, "price": price_or_none(row.unit_price),
         "description": row.description}
        for row in rows
    ]


@router.get("/catalog/picker")
def catalog_picker(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Packages and products for picking order lines: every active package first, then every
    active product. Picking a package is meant to add all the products inside it at once, so
    each package also lists its items with the quantity it carries in that package."""
    packages = db.scalars(
        select(Package).where(Package.is_active).order_by(func.lower(Package.name))
        .options(selectinload(Package.items).selectinload(PackageItem.product))
    ).all()
    products = db.scalars(select(Product).where(Product.is_active).order_by(func.lower(Product.name))).all()
    return [
        {
            "kind": "package", "id": p.id, "name": p.name,
            "price": float(sum((catalog.line_total(item) for item in p.items), start=Decimal(0))),
            "items": [
                {"product_id": item.product_id, "name": item.product.name, "quantity": item.quantity,
                 "unit_price": catalog.unit_price_in_package(item)}
                for item in p.items
            ],
        }
        for p in packages
    ] + [
        {"kind": "product", "id": p.id, "name": p.name, "name_ar": p.name_ar, "price": price_or_none(p.unit_price),
         # daftra_id: how a form naming the products it offers names them (اعمال اضافية), whose
         # list is short enough to show each product's description beside it
         "maintenance_group": p.maintenance_group, "daftra_id": p.daftra_id, "description": p.description or ""}
        for p in products
    ]


# ---------- Daftra's lists ----------

def from_daftra(load, failure: str):
    """A Daftra list, or 502 with the given message when Daftra cannot be reached."""
    try:
        return load()
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, failure)


@router.get("/daftra/staff")
def daftra_staff(user: User = Depends(sales_user)):
    """Names only, for the forms' «staff» fields (اسم المحصل، اسم من اعتمد الخصم)."""
    return from_daftra(daftra.list_staff, "تعذر تحميل الموظفين من دفترة")


@router.get("/daftra/staff_members")
def daftra_staff_members(user: User = Depends(sales_user)):
    """With their ids, for a field that holds the staff member and not just their name (الفني)."""
    return from_daftra(daftra.list_staff_members, "تعذر تحميل الموظفين من دفترة")


@router.get("/daftra/treasuries")
def daftra_treasuries(user: User = Depends(sales_user)):
    return from_daftra(daftra.list_treasuries, "تعذر تحميل الخزائن من دفترة")


@router.get("/daftra/order_sources")
def daftra_order_sources(user: User = Depends(sales_user)):
    return from_daftra(daftra.list_order_sources, "تعذر تحميل مصادر الطلب من دفترة")


def client_category_rows(db: Session) -> list[dict]:
    return [
        {"id": c.id, "name": c.name, "emirate": c.emirate, "area": c.area}
        for c in db.scalars(select(ClientCategory).order_by(ClientCategory.name))
    ]


@router.get("/daftra/client_categories")
def daftra_client_categories(user: User = Depends(sales_user), db: Session = Depends(get_db)):
    """Our copy of Daftra's client categories, each with the الإمارة and المنطقة it fills in."""
    return client_category_rows(db)


@router.get("/daftra/clients/{daftra_id}")
def daftra_client(daftra_id: int, user: User = Depends(sales_user)):
    """What a form needs to know about a client from Daftra itself: their current category, and
    the invoices that still have something to pay (newest first, labelled for the drop-down)."""
    def load():
        invoices = daftra.open_invoices(daftra_id)
        # Where Daftra has this client: it keeps the point on them, which a map link of theirs
        # often does not — a link shared from a phone holds the place's name and nothing else.
        held = daftra_sync.held_custom_fields(daftra_id)
        return {
            "category": daftra.client_category(daftra_id),
            "coordinates": str(held.get(settings.daftra_client_coordinates_field) or "").strip(),
            "open_invoices": [{**invoice, "name": daftra.invoice_label(invoice)} for invoice in invoices],
        }
    return from_daftra(load, "تعذر تحميل بيانات العميل من دفترة")
