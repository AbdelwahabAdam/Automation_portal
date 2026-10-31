"""The products, and the packages built from them.

A product is a single unit with nothing inside it. A package is one or more products sold
together; each line of a package has its own quantity, price and discount.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.errors import Conflict, Invalid, NotFound
from ..audit import changes
from ..audit import log as audit_log
from . import repo
from .in_daftra import place_in_daftra
from .models import Package, PackageItem, Product
from .schemas import PackageIn, ProductIn

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
                    "maintenance_group": p.maintenance_group, "daftra_id": p.daftra_id}
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
        "is_active": product.is_active, "package_count": package_count,
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


def apply_product(db: Session, product: Product, body: ProductIn):
    name = " ".join(body.name.split())
    if not name:
        raise Invalid("اكتب اسم المنتج")
    taken = repo.product_named(db, name)
    if taken is not None and taken is not product:
        raise Conflict("يوجد منتج بنفس الاسم")
    product.name = name
    product.name_ar = body.name_ar.strip()
    product.description = body.description.strip()
    product.unit_price = body.unit_price
    product.is_active = body.is_active
    product.maintenance_group = body.maintenance_group.strip() or None


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
    apply_product(db, product, body)
    old, new = changes(before, product_snapshot(product))
    if new:
        audit_log(db, who, "product.update", "product", product.id, product.name, old, new)
    db.commit()
    return product_out(product, repo.packages_holding(db, product.id))


def delete_product(db: Session, who: Actor, product: Product):
    used = repo.packages_holding(db, product.id)
    if used:
        raise Conflict(f"المنتج داخل {used} باقة فلا يمكن حذفه. أزله من الباقات أولًا أو أوقفه.")
    audit_log(db, who, "product.delete", "product", product.id, product.name, before=product_snapshot(product))
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
            "total": float(line_total(item)),
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
    set_items(package, [
        {"product": products[item.product_id], "quantity": item.quantity, "unit_price": item.unit_price,
         "price_includes_tax": item.price_includes_tax, "discount": item.discount}
        for item in body.items
    ])


def listed_packages(db: Session) -> list[dict]:
    return [package_out(package) for package in repo.packages_with_items(db)]


def create_package(db: Session, who: Actor, body: PackageIn) -> dict:
    package = Package()
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
