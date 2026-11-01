"""Download every product image Daftra holds, so the right file_id can be put on the right product.

Usage: python -m app.jobs download_product_images [--out DIR] [--linked-only] [--no-catalog]

The work order's صورة المنتج (field_30) carries a file id, and a product's `file_id` is where it
comes from (`import_product_images` fills it from the product's default image in Daftra). Nothing
in Daftra's API shows what an image looks like, so a wrong link is invisible until a work order
comes out with the wrong picture on it. This downloads the pictures themselves and writes an
index beside them, and says which links look wrong.

Each file is saved as «<file id> - <product name>.jpg», so the file id is readable from the name,
and `index.csv` lists every image with the product it belongs to in Daftra, the product that
carries it in our catalog, and whether the two agree. The last column, `verdict`, is what to read:

    default      this is the Daftra product's default image, and our catalog points at it
    not-default  our catalog points at this one, but Daftra's default for that product is another
    spare        another image of a product, which nothing points at
    wrong-product our catalog gives this image to a product it does not belong to in Daftra
    missing      (in the report, not the index) a product of ours with no image at all

Options:
    --out DIR       where to put them (default: ./product_images, made if it is not there)
    --linked-only   only the images our catalog's file_ids point at, not every image
    --no-catalog    do not read our database; index what Daftra has and nothing more

Read-only as far as Daftra and our database are concerned: it writes files and nothing else.
"""

import argparse
import csv
import re
import urllib.error
import urllib.request
from pathlib import Path

from sqlalchemy import select

from ..core.config import settings
from ..integrations import daftra
from .registry import job

# Daftra answers the file's own address with a redirect to a signed S3 link, which is the picture
IMAGE_TIMEOUT = 60
SAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def images_of(raw_products: list[dict]) -> list[dict]:
    """Every image of every Daftra product: its file id, its product, and where to fetch it."""
    found = []
    for product in raw_products:
        for image in product.get("ProductImageS3") or []:
            if not str(image.get("id") or "").isdigit():
                continue
            found.append({
                "file_id": int(image["id"]),
                "daftra_id": int(product["id"]),
                "daftra_name": (product.get("name") or "").strip(),
                "is_default": str(image.get("default") or "") == "1",
                "url": image.get("file_full_path") or "",
                "stored_name": image.get("file") or "",
            })
    return found


def file_name(image: dict) -> str:
    """«<file id> - <product name>.jpg»: the id is what a work order carries, so it leads."""
    suffix = Path(image["stored_name"]).suffix.lower() or ".jpg"
    name = SAFE_NAME.sub(" ", image["daftra_name"]).strip() or f"daftra-{image['daftra_id']}"
    return f"{image['file_id']} - {name[:80]}{suffix}"


def download(url: str, into: Path) -> int | None:
    """Saves the picture and returns its size, or None if it could not be fetched."""
    try:
        with urllib.request.urlopen(url, timeout=IMAGE_TIMEOUT) as answer:
            body = answer.read()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    into.write_bytes(body)
    return len(body)


def our_products() -> tuple[dict, list]:
    """{file_id: [our products carrying it]}, and every product of ours, or empty without a database."""
    from ..core.database import SessionLocal
    from ..modules.models import Product

    with SessionLocal() as db:
        products = [{"id": p.id, "name": p.name, "daftra_id": p.daftra_id, "file_id": p.file_id,
                     "is_active": p.is_active}
                    for p in db.scalars(select(Product).order_by(Product.name))]
    carried = {}
    for product in products:
        if product["file_id"]:
            carried.setdefault(product["file_id"], []).append(product)
    return carried, products


def verdict(image: dict, ours: list[dict]) -> str:
    """What the index says about this image, read from the product that carries it in our catalog."""
    if not ours:
        return "default" if image["is_default"] else "spare"
    if any(product["daftra_id"] != image["daftra_id"] for product in ours):
        return "wrong-product"
    return "default" if image["is_default"] else "not-default"


@job("download_product_images", label="تنزيل صور المنتجات", recorded=False,
     about="Downloads every product image from Daftra, to check the file_id of each product")
def _run(db, who):
    """This one is a command line only: `python -m app.jobs download_product_images …`."""
    raise SystemExit("Run it as: python -m app.jobs download_product_images [options]")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="product_images", help="where to put the pictures")
    parser.add_argument("--linked-only", action="store_true", help="only the images our file_ids point at")
    parser.add_argument("--no-catalog", action="store_true", help="do not read our database")
    args = parser.parse_args()

    if settings.daftra_fake:
        raise SystemExit("DAFTRA_FAKE is on, and the fake account has no pictures. Turn it off to download.")

    carried, products = ({}, []) if args.no_catalog else our_products()
    print(f"Reading every product from Daftra ({settings.daftra_subdomain})…")
    images = images_of(daftra.all_records("products", "Product"))
    if args.linked_only:
        images = [image for image in images if image["file_id"] in carried]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows, failed, bytes_saved = [], [], 0
    for index, image in enumerate(sorted(images, key=lambda i: i["file_id"]), start=1):
        ours = carried.get(image["file_id"], [])
        name = file_name(image)
        size = download(image["url"], out / name) if image["url"] else None
        if size is None:
            failed.append(image["file_id"])
        else:
            bytes_saved += size
        rows.append({
            "file_id": image["file_id"],
            "verdict": verdict(image, ours),
            "daftra_id": image["daftra_id"],
            "daftra_name": image["daftra_name"],
            "is_default": "yes" if image["is_default"] else "",
            "our_product_id": ", ".join(str(p["id"]) for p in ours),
            "our_product_name": ", ".join(p["name"] for p in ours),
            "our_product_daftra_id": ", ".join(str(p["daftra_id"]) for p in ours),
            "file": name if size is not None else "",
            "bytes": size or "",
            "url": image["url"],
        })
        if index % 50 == 0:
            print(f"  {index} of {len(images)}…")

    index_file = out / "index.csv"
    with index_file.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["file_id"])
        writer.writeheader()
        writer.writerows(rows)

    saved = len(rows) - len(failed)
    print(f"\n{saved} picture(s) in {out.resolve()}  ({bytes_saved / 1_000_000:.1f} MB), and index.csv beside them")
    if failed:
        print(f"{len(failed)} could not be fetched (file ids): {', '.join(str(i) for i in failed)}")

    # What to fix, which is the point of the download
    wrong = [row for row in rows if row["verdict"] == "wrong-product"]
    if wrong:
        print("\nOur catalog gives these images to a product they do not belong to in Daftra:")
        for row in wrong:
            print(f"  file {row['file_id']} is «{row['daftra_name']}» (daftra {row['daftra_id']}) "
                  f"but carried by «{row['our_product_name']}» (daftra {row['our_product_daftra_id']})")
    not_default = [row for row in rows if row["verdict"] == "not-default"]
    if not_default:
        print(f"\n{len(not_default)} product(s) carry an image that is not their Daftra default — "
              "look at them before running import_product_images, which would replace them.")
    if products:
        linked = {image["file_id"] for image in images}
        no_image = [p for p in products if p["is_active"] and not p["file_id"]]
        gone = [p for p in products if p["file_id"] and p["file_id"] not in linked]
        if no_image:
            print(f"\n{len(no_image)} active product(s) have no image at all:")
            for product in no_image[:40]:
                print(f"  {product['name']} (daftra {product['daftra_id'] or '—'})")
            if len(no_image) > 40:
                print(f"  … and {len(no_image) - 40} more (index.csv has them all)")
        if gone:
            print(f"\n{len(gone)} product(s) carry a file_id that no Daftra product image has any more:")
            for product in gone:
                print(f"  {product['name']} → file {product['file_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
