"""Admin page for the catalog: products, and the packages built from them.

A product is a single unit with nothing inside it. A package is one or more products
sold together; each line of a package has its own quantity, price and discount.
"""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .audit import Audit, changes
from .database import get_db
from .models import Package, PackageItem, Product, User
from .security import require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

CENT = Decimal("0.01")
MAX_PRICE = 99_999_999


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


# ---------- Products ----------

class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    name_ar: str = Field("", max_length=200)
    description: str = Field("", max_length=2000)
    unit_price: Decimal = Field(ge=0, le=MAX_PRICE, decimal_places=2)
    price_includes_tax: bool = True
    tax_rate: Decimal = Field(Decimal("0.05"), ge=0, le=1, decimal_places=4)
    is_active: bool = True
    product_code: str = Field("", max_length=50)
    barcode: str = Field("", max_length=50)
    buy_price: Decimal | None = Field(None, ge=0, le=MAX_PRICE, decimal_places=2)
    stock_balance: int | None = Field(None, ge=0)
    category: str = Field("", max_length=200)
    brand: str = Field("", max_length=100)
    # The product's id in Daftra: the invoices approved requests create use it
    daftra_id: int | None = Field(None, ge=1)
    # Offered as an item on طلب صيانة وتبديل under this group; empty: not offered there
    maintenance_group: str = Field("", max_length=50)


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


def existing_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "المنتج غير موجود")
    return product


def apply_product(product: Product, body: ProductIn, db: Session):
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اكتب اسم المنتج")
    taken = db.scalar(select(Product).where(func.lower(Product.name) == name.lower()))
    if taken is not None and taken is not product:
        raise HTTPException(status.HTTP_409_CONFLICT, "يوجد منتج بنفس الاسم")
    product.name = name
    product.name_ar = body.name_ar.strip()
    product.description = body.description.strip()
    product.unit_price = body.unit_price
    product.price_includes_tax = body.price_includes_tax
    product.tax_rate = body.tax_rate
    product.is_active = body.is_active
    product.product_code = body.product_code.strip()
    product.barcode = body.barcode.strip()
    product.buy_price = body.buy_price
    product.stock_balance = body.stock_balance
    product.category = body.category.strip()
    product.brand = body.brand.strip()
    if body.daftra_id is not None:
        taken = db.scalar(select(Product).where(Product.daftra_id == body.daftra_id))
        if taken is not None and taken is not product:
            raise HTTPException(status.HTTP_409_CONFLICT, f"رقم دفترة {body.daftra_id} مربوط بمنتج آخر: «{taken.name}»")
    product.daftra_id = body.daftra_id
    product.maintenance_group = body.maintenance_group.strip() or None


def package_count(product: Product, db: Session) -> int:
    return db.scalar(select(func.count()).select_from(PackageItem).where(PackageItem.product_id == product.id))


@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(PackageItem.product_id, func.count()).group_by(PackageItem.product_id)).all())
    products = db.scalars(select(Product).order_by(func.lower(Product.name))).all()
    return [product_out(product, counts.get(product.id, 0)) for product in products]


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    product = Product()
    apply_product(product, body, db)
    db.add(product)
    db.flush()
    audit.log(admin, "product.create", "product", product.id, product.name, after=product_snapshot(product))
    db.commit()
    return product_out(product)


@router.put("/products/{product_id}")
def update_product(body: ProductIn, product: Product = Depends(existing_product), admin: User = Depends(require_admin),
                   db: Session = Depends(get_db), audit: Audit = Depends()):
    before = product_snapshot(product)
    apply_product(product, body, db)
    old, new = changes(before, product_snapshot(product))
    if new:
        audit.log(admin, "product.update", "product", product.id, product.name, old, new)
    db.commit()
    return product_out(product, package_count(product, db))


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product: Product = Depends(existing_product), admin: User = Depends(require_admin),
                   db: Session = Depends(get_db), audit: Audit = Depends()):
    used = package_count(product, db)
    if used:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"المنتج داخل {used} باقة فلا يمكن حذفه. أزله من الباقات أولًا أو أوقفه.")
    audit.log(admin, "product.delete", "product", product.id, product.name, before=product_snapshot(product))
    db.delete(product)
    db.commit()


# ---------- Packages ----------

class PackageItemIn(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1, le=9999)
    unit_price: Decimal = Field(ge=0, le=MAX_PRICE, decimal_places=2)
    price_includes_tax: bool = True
    discount: Decimal = Field(Decimal("0"), ge=0, le=MAX_PRICE, decimal_places=2)


class PackageIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field("", max_length=30)
    color: str = Field("", max_length=40)
    is_active: bool = True
    items: list[PackageItemIn] = Field(min_length=1, max_length=100)


def package_out(package: Package) -> dict:
    items = [
        {
            "product_id": item.product_id, "product_name": item.product.name, "product_name_ar": item.product.name_ar,
            "quantity": item.quantity, "unit_price": float(item.unit_price),
            "price_includes_tax": item.price_includes_tax, "discount": float(item.discount),
            "total": float(line_total(item)),
        }
        for item in package.items
    ]
    return {
        "id": package.id, "code": package.code or "", "name": package.name, "color": package.color,
        "is_active": package.is_active, "items": items, "total": round(sum(item["total"] for item in items), 2),
    }


def package_snapshot(package: Package) -> dict:
    out = package_out(package)
    return {
        "name": out["name"], "code": out["code"], "color": out["color"], "is_active": out["is_active"],
        "total": out["total"],
        "items": [f'{item["product_name"]} × {item["quantity"]} = {item["total"]:g}' for item in out["items"]],
    }


def existing_package(package_id: int, db: Session = Depends(get_db)) -> Package:
    package = db.get(Package, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الباقة غير موجودة")
    return package


def apply_package(package: Package, body: PackageIn, db: Session):
    name = " ".join(body.name.split())
    code = body.code.strip() or None
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اكتب اسم الباقة")
    taken = db.scalar(select(Package).where(func.lower(Package.name) == name.lower()))
    if taken is not None and taken is not package:
        raise HTTPException(status.HTTP_409_CONFLICT, "توجد باقة بنفس الاسم")
    if code:
        taken = db.scalar(select(Package).where(func.lower(Package.code) == code.lower()))
        if taken is not None and taken is not package:
            raise HTTPException(status.HTTP_409_CONFLICT, "الكود مستخدم لباقة أخرى")
    product_ids = [item.product_id for item in body.items]
    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "المنتج مكرر في الباقة؛ زِد الكمية بدل تكراره")
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))}
    if len(products) != len(product_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "أحد المنتجات المختارة غير موجود")
    for item in body.items:
        if item.discount > item.unit_price * item.quantity * (1 + products[item.product_id].tax_rate):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                f"خصم «{products[item.product_id].name}» أكبر من قيمة البند")
    package.name = name
    package.code = code
    package.color = body.color.strip()
    package.is_active = body.is_active
    set_items(package, [
        {"product": products[item.product_id], "quantity": item.quantity, "unit_price": item.unit_price,
         "price_includes_tax": item.price_includes_tax, "discount": item.discount}
        for item in body.items
    ])


@router.get("/packages")
def list_packages(db: Session = Depends(get_db)):
    packages = db.scalars(
        select(Package).options(selectinload(Package.items).selectinload(PackageItem.product)).order_by(Package.code, Package.name)
    )
    return [package_out(package) for package in packages]


@router.post("/packages", status_code=status.HTTP_201_CREATED)
def create_package(body: PackageIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    package = Package()
    apply_package(package, body, db)
    db.add(package)
    db.flush()
    audit.log(admin, "package.create", "package", package.id, package.name, after=package_snapshot(package))
    db.commit()
    return package_out(package)


@router.put("/packages/{package_id}")
def update_package(body: PackageIn, package: Package = Depends(existing_package), admin: User = Depends(require_admin),
                   db: Session = Depends(get_db), audit: Audit = Depends()):
    before = package_snapshot(package)
    apply_package(package, body, db)
    db.flush()
    db.refresh(package)
    old, new = changes(before, package_snapshot(package))
    if new:
        audit.log(admin, "package.update", "package", package.id, package.name, old, new)
    db.commit()
    return package_out(package)


@router.delete("/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(package: Package = Depends(existing_package), admin: User = Depends(require_admin),
                   db: Session = Depends(get_db), audit: Audit = Depends()):
    audit.log(admin, "package.delete", "package", package.id, package.name, before=package_snapshot(package))
    db.delete(package)
    db.commit()

