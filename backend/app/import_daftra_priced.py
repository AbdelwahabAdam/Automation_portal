"""Top up the catalog with the Daftra products that actually carry a price.

Usage: python -m app.import_daftra_priced <products.json>

Daftra's product list is mostly placeholders with no price (and plenty of duplicate names);
only a handful of its rows carry a real one, usually for items no quotation workbook ever
covered (chillers, water heaters, tank cleaning). This adds those as products, or — since
Daftra is the source of truth for price — updates the price of one already in the catalog
under the same name. Safe to run again.
"""

import argparse
import json
from decimal import Decimal

from sqlalchemy import select

from .database import SessionLocal, run_migrations
from .models import Product

DEFAULT_TAX_RATE = Decimal("0.05")


def same_name(name: str) -> str:
    return "".join(name.split()).lower()


def priced_products(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        rows = json.load(f)["data"]
    found = []
    for row in rows:
        product = row["Product"]
        if product.get("status") != "0" or product.get("deactivate") != "0":
            continue
        price = Decimal(str(product.get("unit_price") or 0))
        if price <= 0:
            continue
        name = " ".join((product.get("name") or "").split())
        if not name:
            continue
        found.append({"name": name, "price": price, "description": " ".join((product.get("description") or "").split())})
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("products_json")
    args = parser.parse_args()

    rows = priced_products(args.products_json)
    run_migrations()
    with SessionLocal() as db:
        existing = {same_name(p.name): p for p in db.scalars(select(Product))}
        added, updated = [], []
        for row in rows:
            key = same_name(row["name"])
            product = existing.get(key)
            if product is None:
                product = Product(name=row["name"], price_includes_tax=True, tax_rate=DEFAULT_TAX_RATE)
                existing[key] = product
                added.append(row["name"])
            elif product.unit_price != row["price"]:
                updated.append(f"{product.name}: {product.unit_price} -> {row['price']}")
            product.unit_price = row["price"]
            if not product.description:
                product.description = row["description"]
            db.add(product)
        db.commit()
    print(f"{len(rows)} priced Daftra products checked")
    if added:
        print("Added:\n" + "\n".join(f"  {name}" for name in added))
    if updated:
        print("Price updated (Daftra is the source of truth):\n" + "\n".join(f"  {name}" for name in updated))


if __name__ == "__main__":
    main()
