"""The queries on the catalog's own tables. No commits, no decisions."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import Package, PackageItem, Product


def product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def package(db: Session, package_id: int) -> Package | None:
    return db.get(Package, package_id)


def products_by_name(db: Session) -> list[Product]:
    return list(db.scalars(select(Product).order_by(func.lower(Product.name))))


def active_products(db: Session) -> list[Product]:
    return list(db.scalars(select(Product).where(Product.is_active).order_by(func.lower(Product.name))))


def packages_with_items(db: Session) -> list[Package]:
    return list(db.scalars(
        select(Package).options(selectinload(Package.items).selectinload(PackageItem.product))
        .order_by(Package.code, Package.name)
    ))


def active_packages_by_name(db: Session) -> list[Package]:
    """For the order-lines picker, which lists them by name rather than by code."""
    return list(db.scalars(
        select(Package).options(selectinload(Package.items).selectinload(PackageItem.product))
        .where(Package.is_active).order_by(func.lower(Package.name))
    ))


def product_named(db: Session, name: str) -> Product | None:
    return db.scalar(select(Product).where(func.lower(Product.name) == name.lower()))


def product_with_daftra_id(db: Session, daftra_id: int) -> Product | None:
    return db.scalar(select(Product).where(Product.daftra_id == daftra_id))


def package_named(db: Session, name: str) -> Package | None:
    return db.scalar(select(Package).where(func.lower(Package.name) == name.lower()))


def package_coded(db: Session, code: str) -> Package | None:
    return db.scalar(select(Package).where(func.lower(Package.code) == code.lower()))


def products_by_id(db: Session, ids: list[int]) -> dict[int, Product]:
    return {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ids)))}


def packages_holding(db: Session, product_id: int) -> int:
    """How many packages a product is inside; one that is used cannot be deleted."""
    return db.scalar(select(func.count()).select_from(PackageItem).where(PackageItem.product_id == product_id))


def package_counts(db: Session) -> dict[int, int]:
    """How many packages each product is in, for the products list."""
    return dict(db.execute(select(PackageItem.product_id, func.count()).group_by(PackageItem.product_id)).all())


def items_of_active_packages(db: Session) -> list[PackageItem]:
    """Every line of every active package, for the prices a submitted form is checked against."""
    return list(db.scalars(
        select(PackageItem).join(Package).where(Package.is_active)
        .options(selectinload(PackageItem.product))
    ))
