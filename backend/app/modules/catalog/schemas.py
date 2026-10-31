"""What the catalog page sends in."""

from decimal import Decimal

from pydantic import BaseModel, Field

MAX_PRICE = 99_999_999


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    name_ar: str = Field("", max_length=200)
    description: str = Field("", max_length=2000)
    unit_price: Decimal = Field(ge=0, le=MAX_PRICE, decimal_places=2)
    is_active: bool = True
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
    color: str = Field("", max_length=40)
    is_active: bool = True
    items: list[PackageItemIn] = Field(min_length=1, max_length=100)
