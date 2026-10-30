"""What the catalog page sends in."""

from decimal import Decimal

from pydantic import BaseModel, Field

MAX_PRICE = 99_999_999


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
