"""Replace the whole catalog with the final one in Products.xlsx (sheets "Packages" and "Items").

Usage: python -m app.import_final_catalog [path-to-Products.xlsx]

Products.xlsx is the single source of truth for the catalog: every product, package and
package-to-product link is deleted and rebuilt from it. Unlike import_products.py (which only
adds to or updates the catalog), this empties products/packages/product_to_package first — run
it only when the workbook is meant to replace the catalog, not extend it. Products are matched
by the "SKU البند" (FL-I0xx) column and packages by "SKU المنتج / الباقة" (FL-P0xx...), so a
rerun after only editing the workbook still assigns the same ids.
"""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal

from openpyxl import load_workbook

from .catalog import set_items
from .core.database import SessionLocal, run_migrations
from .models import Package, PackageItem, Product

DEFAULT_TAX_RATE = Decimal("0.05")
COLOR_WORDS = ["أبيض", "أسود", "ذهبي"]


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def guess_color(name: str) -> str:
    return next((word for word in COLOR_WORDS if word in name), "")


def read_workbook(path: str):
    wb = load_workbook(path, data_only=True)
    packages = [dict(zip(("sku", "name", "total", "sale_type"), row))
                for row in wb["Packages"].iter_rows(min_row=2, values_only=True) if row[0]]
    items = [dict(zip(("package_sku", "item_sku", "name", "total", "_blank", "source_name", "source_meaning"), row))
             for row in wb["Items"].iter_rows(min_row=2, values_only=True) if row[1]]
    return packages, items


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workbook", nargs="?", default="../../Products.xlsx")
    args = parser.parse_args()

    packages, items = read_workbook(args.workbook)
    run_migrations()

    by_item_sku = defaultdict(list)
    for item in items:
        by_item_sku[item["item_sku"]].append(item)
    by_package_sku = defaultdict(list)
    for item in items:
        by_package_sku[item["package_sku"]].append(item)

    with SessionLocal() as db:
        # The catalog is rebuilt from scratch every run; product_to_package first (it points at both)
        db.query(PackageItem).delete()
        db.query(Package).delete()
        db.query(Product).delete()
        db.flush()

        products = {}
        for sku, lines in by_item_sku.items():
            price, _count = Counter(money(line["total"]) for line in lines).most_common(1)[0]
            first = lines[0]
            product = Product(
                sku=sku, name=str(first["name"]).strip(), name_ar=str(first["source_meaning"] or "").strip(),
                description=f"المصدر: {first['source_name']}", unit_price=price,
                price_includes_tax=True, tax_rate=DEFAULT_TAX_RATE, is_active=True,
            )
            db.add(product)
            products[sku] = product
        db.flush()  # products need their ids before package_items can reference them

        for pkg in packages:
            package = Package(
                code=pkg["sku"], name=str(pkg["name"]).strip(), color=guess_color(str(pkg["name"])), is_active=True,
            )
            db.add(package)
            db.flush()
            lines = by_package_sku.get(pkg["sku"], [])
            set_items(package, [
                {"product": products[line["item_sku"]], "quantity": 1, "unit_price": money(line["total"]),
                 "price_includes_tax": True, "discount": Decimal("0")}
                for line in lines
            ])

        db.commit()
        print(f"Catalog replaced: {len(products)} products, {len(packages)} packages, "
              f"{sum(len(v) for v in by_package_sku.values())} links")


if __name__ == "__main__":
    main()
