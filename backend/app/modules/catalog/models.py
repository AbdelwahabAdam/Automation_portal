"""The tables catalog owns: the products, the packages, and what is in each package."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base


class Product(Base):
    """A single unit that is sold or installed, with nothing else inside it."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Its id in the final catalog workbook (e.g. "FL-I012"), so a re-import matches by it, not by name
    sku: Mapped[str | None] = mapped_column(String(20), unique=True)
    # Daftra's own product id, so a re-import from products.json matches the same row, not by name
    daftra_id: Mapped[int | None] = mapped_column(unique=True)
    # Its image in Daftra (ProductImageS3), as a file id: what the work order's صورة المنتج holds
    file_id: Mapped[int | None]
    # As written on quotations and invoices
    name: Mapped[str] = mapped_column(String(200), unique=True)
    name_ar: Mapped[str] = mapped_column(String(200), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    # The usual price; a package line can charge a different one
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    price_includes_tax: Mapped[bool] = mapped_column(default=True, server_default="true")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.05"), server_default="0.05")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Daftra reference fields, kept for traceability; filled from Daftra, not typed in
    product_code: Mapped[str | None] = mapped_column(String(50))
    barcode: Mapped[str | None] = mapped_column(String(50))
    buy_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    stock_balance: Mapped[int | None]
    category: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100))
    # Offered as an item on طلب صيانة وتبديل under this group (e.g. «الفلاتر»); None: not offered there
    maintenance_group: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Package(Base):
    """One or more products sold together under one name, e.g. a cooler with its cover, filter and fitting."""

    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Short reference such as FLP-001; optional
    code: Mapped[str | None] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    color: Mapped[str] = mapped_column(String(40), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["PackageItem"]] = relationship(
        back_populates="package", cascade="all, delete-orphan", order_by="PackageItem.sort_order"
    )


class PackageItem(Base):
    """A product inside a package, with the quantity and price it has in that package."""

    __tablename__ = "product_to_package"

    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True, index=True)
    quantity: Mapped[int] = mapped_column(default=1, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_includes_tax: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Taken off this line's total, tax included
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")

    package: Mapped[Package] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
