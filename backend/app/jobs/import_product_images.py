"""Fill each product's file_id: its image in Daftra, for the work order's صورة المنتج (field_30).

Usage: python -m app.import_product_images [path-to-a-products-export.json]

With no argument, reads every product live from Daftra. With a path, reads a saved products
export instead (the shape GET /products.json returns), for offline use.

A product is matched by its daftra_id, and takes the first id in that Daftra product's
ProductImageS3 (its default image). Products without a daftra_id, or whose Daftra product has no
image, are left as they are and reported. Safe to run again.
"""

import argparse
import json

from sqlalchemy import select

from ..integrations import daftra
from ..core.database import SessionLocal, run_migrations
from ..modules.models import Product
from .registry import job


def images_by_product(raw_products: list[dict]) -> dict[int, int]:
    """Daftra product id -> the file id of its first (default) image."""
    found = {}
    for product in raw_products:
        images = product.get("ProductImageS3") or []
        if images and str(images[0].get("id") or "").isdigit():
            found[int(product["id"])] = int(images[0]["id"])
    return found



@job("import_product_images", label="صور المنتجات", recorded=False,
     about="Links each product to its image in Daftra")
def _run(db, who):
    """This one is a command line only: `python -m app.jobs import_product_images …`."""
    raise SystemExit("Run it as: python -m app.jobs import_product_images [options]")

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("products_json", nargs="?", help="a saved products export; omit to read live from Daftra")
    args = parser.parse_args()

    if args.products_json:
        with open(args.products_json, encoding="utf-8-sig") as f:
            raw = [row["Product"] for row in json.load(f)["data"]]
    else:
        raw = daftra.all_records("products", "Product")
    images = images_by_product(raw)

    run_migrations()
    with SessionLocal() as db:
        products = db.scalars(select(Product)).all()
        changed, no_image, no_link = 0, [], []
        for product in products:
            if product.daftra_id is None:
                no_link.append(product.name)
                continue
            file_id = images.get(product.daftra_id)
            if file_id is None:
                no_image.append(f"{product.name} (daftra {product.daftra_id})")
            elif product.file_id != file_id:
                product.file_id = file_id
                changed += 1
        db.commit()
    print(f"{len(products)} products, {changed} given a new file_id")
    if no_link:
        print("No daftra_id, so no image:\n" + "\n".join(f"  {name}" for name in no_link))
    if no_image:
        print("Their Daftra product has no image:\n" + "\n".join(f"  {name}" for name in no_image))


if __name__ == "__main__":
    main()
