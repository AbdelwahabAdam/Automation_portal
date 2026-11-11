"""The products, and the packages built from them.

A product is a single unit with nothing inside it. A package is one or more products sold
together; each line of a package has its own quantity, price and discount.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.errors import Conflict, Invalid, NotFound
from ...core.text import squash
from ..audit import changes
from ..audit import log as audit_log
from . import repo
from .in_daftra import (delete_in_daftra, edit_in_daftra, is_service, place_in_daftra,
                        product_image, read_in_daftra)
from .models import Package, PackageItem, Product
from .schemas import PackageIn, ProductIn
from .sync import daftra_price

CENT = Decimal("0.01")


# ---------- What a line and a package cost ----------


def line_total(item: PackageItem) -> Decimal:
    """What the line costs the customer: quantity x price with tax, minus the line's discount."""
    gross = item.unit_price * item.quantity
    if not item.price_includes_tax:
        gross *= 1 + item.product.tax_rate
    return (gross - item.discount).quantize(CENT, ROUND_HALF_UP)


def unit_price_in_package(item: PackageItem) -> float:
    """What one unit of a product costs inside a package, tax included and after the line's discount."""
    return round(float(line_total(item)) / item.quantity, 2)


def set_items(package: Package, lines: list[dict]):
    """Makes the package contain exactly these lines, each a dict of PackageItem values including "product".

    Lines already there are changed in place: replacing them with new rows would insert
    a row with the same key before the old one is deleted.
    """
    current = {item.product_id: item for item in package.items if item.product_id is not None}
    kept = []
    for position, line in enumerate(lines, start=1):
        item = current.get(line["product"].id) if line["product"].id is not None else None
        if item is None:
            item = PackageItem(package=package)
        for name, value in line.items():
            setattr(item, name, value)
        item.sort_order = position
        kept.append(item)
    package.items = kept


# ---------- What a submitted form is checked against ----------


def active_products_for_forms(db: Session) -> dict:
    """Our own catalog's active products, keyed by id (as a string, to match the "<field>_id"
    sent from the form)."""
    return {
        str(p.id): {"id": p.id, "name": p.name, "price": float(p.unit_price) if p.unit_price else 0,
                    "maintenance_group": p.maintenance_group, "daftra_id": p.daftra_id, "open_price": p.open_price}
        for p in repo.active_products(db)
    }


def package_prices(db: Session) -> dict:
    """{(package id, product id): unit price}, both ids as strings like the order lines hold them."""
    return {(str(item.package_id), str(item.product_id)): unit_price_in_package(item)
            for item in repo.items_of_active_packages(db)}


# ---------- Products ----------


def product_out(product: Product, package_count: int = 0) -> dict:
    return {
        "id": product.id, "sku": product.sku, "daftra_id": product.daftra_id,
        "name": product.name, "name_ar": product.name_ar,
        "description": product.description, "unit_price": float(product.unit_price),
        "price_includes_tax": product.price_includes_tax, "tax_rate": float(product.tax_rate),
        "is_active": product.is_active, "package_count": package_count, "open_price": product.open_price,
        "product_code": product.product_code or "", "barcode": product.barcode or "",
        "buy_price": float(product.buy_price) if product.buy_price is not None else None,
        "stock_balance": product.stock_balance, "category": product.category or "",
        "brand": product.brand or "", "maintenance_group": product.maintenance_group or "",
    }


def product_snapshot(product: Product) -> dict:
    return {key: value for key, value in product_out(product).items() if key not in ("id", "package_count")}


def product_by_id(db: Session, product_id: int) -> Product:
    product = repo.product(db, product_id)
    if product is None:
        raise NotFound("المنتج غير موجود")
    return product


def apply_product(db: Session, product: Product, body: ProductIn, from_daftra: bool = False):
    """from_daftra: the save has just pointed the product at another Daftra product and taken that
    one's name, price and description, so what the drawer still showed for those is passed over."""
    if not from_daftra:
        name = " ".join(body.name.split())
        if not name:
            raise Invalid("اكتب اسم المنتج")
        taken = repo.product_named(db, name)
        if taken is not None and taken is not product:
            raise Conflict("يوجد منتج بنفس الاسم")
        product.name = name
        product.description = body.description.strip()
    product.name_ar = body.name_ar.strip()
    product.open_price = body.open_price
    # Its price is typed on each order line, and its text starts the line: so it has no price of its
    # own, and must have a text
    product.unit_price = 0 if body.open_price else (product.unit_price if from_daftra else body.unit_price)
    if body.open_price and not product.description:
        raise Invalid("اكتب نص البند: يبدأ به السطر في الطلب ويظهر في الفاتورة")
    product.is_active = body.is_active
    product.maintenance_group = body.maintenance_group.strip() or None


def relink_product(db: Session, product: Product, daftra_id: int):
    """Points the product at another Daftra product, and takes that one's name, price, description,
    code and picture.

    Changing the number is a correction — «this row was pointing at the wrong product» — so Daftra
    is what is right and the catalog row follows it, the same way «مزامنة من دفترة» would. The
    picture goes with it: `file_id` is what the work order prints, and the old one belongs to the
    product that is no longer linked. Nothing is sent to Daftra: neither product is changed there.
    """
    taken = repo.product_with_daftra_id(db, daftra_id)
    if taken is not None and taken is not product:
        raise Conflict(f"منتج دفترة رقم {daftra_id} مربوط بمنتج آخر: «{taken.name}»")
    source = read_in_daftra(daftra_id)
    if not is_service(source):
        raise Conflict(f"منتج دفترة رقم {daftra_id} منتج مخزون لا خدمة، فلا يُربط به. "
                       "منتجات الكتالوج تُربط بالخدمات.")
    name = squash(source.get("name"))
    if name:
        clash = repo.product_named(db, name)
        if clash is not None and clash is not product:
            raise Conflict(f"اسمه في دفترة «{name}» مستخدم لمنتج آخر في البوابة، فلم يُربط.")
        product.name = name
    price = daftra_price(source.get("unit_price"))
    if price is not None:
        product.unit_price = price
    description = (source.get("description") or "").strip()
    if description:
        product.description = description
    picture = product_image(daftra_id, source)
    product.file_id = picture["file_id"] if picture else None
    product.product_code = source.get("product_code") or ""
    product.barcode = source.get("barcode") or None
    product.daftra_id = daftra_id


def daftra_product(db: Session, daftra_id: int) -> dict:
    """A Daftra product as the edit drawer shows it beside the number: what the link would become."""
    source = read_in_daftra(daftra_id)
    picture = product_image(daftra_id, source)
    holder = repo.product_with_daftra_id(db, daftra_id)
    price = daftra_price(source.get("unit_price"))
    return {
        "daftra_id": daftra_id,
        "name": squash(source.get("name")),
        "unit_price": float(price) if price is not None else None,
        "description": (source.get("description") or "").strip(),
        "product_code": source.get("product_code") or "",
        "is_service": is_service(source),
        "file_id": picture["file_id"] if picture else None,
        "image_url": picture["url"] if picture else "",
        "linked_to": {"id": holder.id, "name": holder.name} if holder is not None else None,
    }


def listed_products(db: Session) -> list[dict]:
    counts = repo.package_counts(db)
    return [product_out(product, counts.get(product.id, 0)) for product in repo.products_by_name(db)]


def create_product(db: Session, who: Actor, body: ProductIn) -> dict:
    product = Product()
    apply_product(db, product, body)
    place_in_daftra(db, product)
    db.add(product)
    db.flush()
    audit_log(db, who, "product.create", "product", product.id, product.name, after=product_snapshot(product))
    db.commit()
    return product_out(product)


def update_product(db: Session, who: Actor, product: Product, body: ProductIn) -> dict:
    before = product_snapshot(product)
    # A save that points the product at another Daftra product reads from Daftra instead of
    # writing to it: the new product keeps its own name, price and description, and ours take them
    relinking = body.daftra_id is not None and body.daftra_id != product.daftra_id
    if relinking:
        relink_product(db, product, body.daftra_id)
    apply_product(db, product, body, from_daftra=relinking)
    old, new = changes(before, product_snapshot(product))
    # Daftra first: if it refuses, nothing here is saved either
    if not relinking:
        edit_in_daftra(product, new)
    if new:
        audit_log(db, who, "product.update", "product", product.id, product.name, old, new)
    db.commit()
    return product_out(product, repo.packages_holding(db, product.id))


def delete_product(db: Session, who: Actor, product: Product, from_daftra: bool = False):
    """from_daftra: also delete the Daftra product it is linked to; otherwise that one stays."""
    used = repo.packages_holding(db, product.id)
    if used:
        raise Conflict(f"المنتج داخل {used} باقة فلا يمكن حذفه. أزله من الباقات أولًا أو أوقفه.")
    deleted_there = from_daftra and product.daftra_id is not None
    if deleted_there:
        delete_in_daftra(product)
    audit_log(db, who, "product.delete", "product", product.id, product.name, before=product_snapshot(product),
              after={"deleted_in_daftra": product.daftra_id} if deleted_there else None)
    db.delete(product)
    db.commit()


# ---------- Packages ----------


def package_out(package: Package) -> dict:
    items = [
        {
            "product_id": item.product_id, "product_name": item.product.name,
            "product_name_ar": item.product.name_ar,
            "quantity": item.quantity, "unit_price": float(item.unit_price),
            "price_includes_tax": item.price_includes_tax, "discount": float(item.discount),
            "total": float(line_total(item)), "open_price": item.product.open_price,
        }
        for item in package.items
    ]
    return {
        "id": package.id, "code": package.code or "", "name": package.name, "color": package.color,
        "is_active": package.is_active, "items": items,
        "total": round(sum(item["total"] for item in items), 2),
    }


def package_snapshot(package: Package) -> dict:
    out = package_out(package)
    return {
        "name": out["name"], "code": out["code"], "color": out["color"], "is_active": out["is_active"],
        "total": out["total"],
        "items": [f'{item["product_name"]} × {item["quantity"]} = {item["total"]:g}' for item in out["items"]],
    }


def package_by_id(db: Session, package_id: int) -> Package:
    package = repo.package(db, package_id)
    if package is None:
        raise NotFound("الباقة غير موجودة")
    return package


def apply_package(db: Session, package: Package, body: PackageIn):
    name = " ".join(body.name.split())
    if not name:
        raise Invalid("اكتب اسم الباقة")
    taken = repo.package_named(db, name)
    if taken is not None and taken is not package:
        raise Conflict("توجد باقة بنفس الاسم")
    product_ids = [item.product_id for item in body.items]
    if len(set(product_ids)) != len(product_ids):
        raise Invalid("المنتج مكرر في الباقة؛ زِد الكمية بدل تكراره")
    products = repo.products_by_id(db, product_ids)
    if len(products) != len(product_ids):
        raise Invalid("أحد المنتجات المختارة غير موجود")
    for item in body.items:
        if item.discount > item.unit_price * item.quantity * (1 + products[item.product_id].tax_rate):
            raise Invalid(f"خصم «{products[item.product_id].name}» أكبر من قيمة البند")
    package.name = name
    package.color = body.color.strip()
    package.is_active = body.is_active
    # A product with no fixed price is priced on the order, so inside a package too: it adds
    # nothing to the package's own price here
    set_items(package, [
        {"product": products[item.product_id], "quantity": item.quantity,
         "unit_price": Decimal(0) if products[item.product_id].open_price else item.unit_price,
         "price_includes_tax": item.price_includes_tax,
         "discount": Decimal(0) if products[item.product_id].open_price else item.discount}
        for item in body.items
    ])


def listed_packages(db: Session) -> list[dict]:
    return [package_out(package) for package in repo.packages_with_items(db)]


# The reference a package is known by outside the portal. The catalog import hands these out by
# position (jobs/import_catalog), and a package added here takes the next free one, so it is listed
# and searched for like the rest instead of showing a dash.
CODE_PREFIX = "FLP-"
CODE_NUMBER = re.compile(rf"^{CODE_PREFIX}(\d+)$")


def next_package_code(db: Session) -> str:
    """FLP-046 after FLP-045: one past the highest number given out.

    Only codes of that shape are counted, so one written by hand in another shape is passed over
    rather than breaking the counting. Three digits until the number outgrows them (FLP-1000).
    """
    highest = max((int(found.group(1)) for code in repo.package_codes(db)
                   if (found := CODE_NUMBER.match(code))), default=0)
    return f"{CODE_PREFIX}{highest + 1:03d}"


def create_package(db: Session, who: Actor, body: PackageIn) -> dict:
    package = Package(code=next_package_code(db))
    apply_package(db, package, body)
    db.add(package)
    db.flush()
    audit_log(db, who, "package.create", "package", package.id, package.name, after=package_snapshot(package))
    db.commit()
    return package_out(package)


def update_package(db: Session, who: Actor, package: Package, body: PackageIn) -> dict:
    before = package_snapshot(package)
    apply_package(db, package, body)
    db.flush()
    db.refresh(package)
    old, new = changes(before, package_snapshot(package))
    if new:
        audit_log(db, who, "package.update", "package", package.id, package.name, old, new)
    db.commit()
    return package_out(package)


def delete_package(db: Session, who: Actor, package: Package):
    audit_log(db, who, "package.delete", "package", package.id, package.name, before=package_snapshot(package))
    db.delete(package)
    db.commit()
