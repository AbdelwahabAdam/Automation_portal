"""The catalog: the admin page that keeps it, and what the forms pick from. Transport only."""

from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.database import get_db
from ...core.security import acting, form_user, require
from . import repo, service
from .models import Package, Product
from .schemas import PackageIn, ProductIn

# The admin page that keeps the catalog
may_keep = require("admin.catalog")
admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(may_keep)])
# What the forms pick from
router = APIRouter(prefix="/api")


def price_or_none(value) -> float | None:
    return float(value) if value else None


def existing_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    return service.product_by_id(db, product_id)


def existing_package(package_id: int, db: Session = Depends(get_db)) -> Package:
    return service.package_by_id(db, package_id)


# ---------- The admin page ----------


@admin_router.get("/products")
def list_products(db: Session = Depends(get_db)):
    return service.listed_products(db)


@admin_router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn, who: Actor = Depends(acting(may_keep)), db: Session = Depends(get_db)):
    return service.create_product(db, who, body)


@admin_router.put("/products/{product_id}")
def update_product(body: ProductIn, product: Product = Depends(existing_product),
                   who: Actor = Depends(acting(may_keep)), db: Session = Depends(get_db)):
    return service.update_product(db, who, product, body)


@admin_router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product: Product = Depends(existing_product), who: Actor = Depends(acting(may_keep)),
                   db: Session = Depends(get_db)):
    service.delete_product(db, who, product)


@admin_router.get("/packages")
def list_packages(db: Session = Depends(get_db)):
    return service.listed_packages(db)


@admin_router.post("/packages", status_code=status.HTTP_201_CREATED)
def create_package(body: PackageIn, who: Actor = Depends(acting(may_keep)), db: Session = Depends(get_db)):
    return service.create_package(db, who, body)


@admin_router.put("/packages/{package_id}")
def update_package(body: PackageIn, package: Package = Depends(existing_package),
                   who: Actor = Depends(acting(may_keep)), db: Session = Depends(get_db)):
    return service.update_package(db, who, package, body)


@admin_router.delete("/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(package: Package = Depends(existing_package), who: Actor = Depends(acting(may_keep)),
                   db: Session = Depends(get_db)):
    service.delete_package(db, who, package)


# ---------- What the forms pick from ----------


@router.get("/products")
def products_for_sales(user=Depends(form_user), db: Session = Depends(get_db)):
    """Our own catalog, for the product field's search box (not Daftra's, which carries duplicate names)."""
    return [
        {"id": row.id, "name": row.name, "name_ar": row.name_ar, "price": price_or_none(row.unit_price),
         "description": row.description}
        for row in repo.active_products(db)
    ]


@router.get("/catalog/picker")
def catalog_picker(user=Depends(form_user), db: Session = Depends(get_db)):
    """Packages and products for picking order lines: every active package first, then every
    active product. Picking a package is meant to add all the products inside it at once, so
    each package also lists its items with the quantity it carries in that package."""
    return [
        {
            "kind": "package", "id": p.id, "name": p.name,
            "price": float(sum((service.line_total(item) for item in p.items), start=Decimal(0))),
            "items": [
                {"product_id": item.product_id, "name": item.product.name, "quantity": item.quantity,
                 "unit_price": service.unit_price_in_package(item)}
                for item in p.items
            ],
        }
        for p in repo.active_packages_by_name(db)
    ] + [
        # daftra_id: how a form naming the products it offers names them (اعمال اضافية), whose
        # list is short enough to show each product's description beside it
        {"kind": "product", "id": p.id, "name": p.name, "name_ar": p.name_ar,
         "price": price_or_none(p.unit_price), "maintenance_group": p.maintenance_group,
         "daftra_id": p.daftra_id, "description": p.description or ""}
        for p in repo.active_products(db)
    ]
