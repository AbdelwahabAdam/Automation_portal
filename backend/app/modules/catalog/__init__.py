"""The products and the packages built from them.

A product is a single unit with nothing inside it; a package is one or more products sold
together, each line with its own quantity, price and discount.
"""

from fastapi import APIRouter

from . import repo
from .models import Package, PackageItem, Product
from .router import admin_router
from .router import router as sales_router
from .service import active_products_for_forms, line_total, package_prices, unit_price_in_package
from .sync import has_linked_products, sync_from_daftra

router = APIRouter()
router.include_router(admin_router)
router.include_router(sales_router)

__all__ = ["Package", "PackageItem", "Product", "active_products_for_forms", "has_linked_products",
           "line_total", "package_prices", "repo", "router", "sync_from_daftra",
           "unit_price_in_package"]
