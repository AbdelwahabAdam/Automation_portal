"""Replace the whole catalog from the Proposal quotation PDFs and Daftra's products.json.

Usage: python -m app.import_packages_from_proposals [--proposals-dir ../../Proposals]
                                                      [--products-json ../../products.json]
                                                      [--dry-run]

Each PDF in Proposals/ is a Daftra quotation for one package: its item table gives the
package's products, quantities and prices. PACKAGE_PDFS below maps the business's package
names to the PDF that defines them (built by hand — see the comment above it). This empties
products/packages/product_to_package and rebuilds them, same as import_final_catalog.py, so
run it only when the PDFs + products.json should overwrite the catalog, not add to it.

Each item's name is matched against products.json (by exact name once whitespace/case is
normalized, the same approach import_daftra_priced.py and import_products.py already use) to
pull in Daftra's id, product_code, barcode, buy_price, stock_balance, category and brand. An
item that doesn't match any Daftra product is still added (name + PDF price only) and listed
in the "not found in Daftra" section of the report, instead of guessing.

Always run with --dry-run first and read the report before the real run.
"""

import argparse
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pdfplumber

from . import daftra as daftra_api
from .catalog import set_items
from .database import SessionLocal, run_migrations
from .models import Package, PackageItem, Product

DEFAULT_TAX_RATE = Decimal("0.05")
COLOR_WORDS = {"أبيض": "White", "أسود": "Black", "ذهبي": "Gold"}

# Package name -> PDF filename (None = no quotation yet; the package is created empty).
# Built by hand against the 38 files in Proposals/: most packages map 1:1 to a PDF by the
# product they describe; a few notes worth knowing before re-running this after edits:
#   - "باقة برادة سقيا الخير - 2 صنبور - ذهبي" has no PDF (no 2-tap gold Saqya Al Khair
#     quotation exists yet) -> created as an empty package.
#   - The six "سقيا الخير مدمجة" entries are two near-duplicate wordings (برادتا vs برادة)
#     of the same three colours, so they map to the same three PDFs twice. Flagged in the
#     report too -- worth checking with the business whether both wordings should stay.
PACKAGE_PDFS = {
    "باقة برادة نبع المزن - 2 صنبور - أبيض": "عرض سعر براده نبع المزن 2 ولف ابيض.pdf",
    "باقة برادة نبع المزن - 2 صنبور - أسود": "عرض سعر براده نبع المزن 2ولف اسود.pdf",
    "باقة برادة نبع المزن - 2 صنبور - ذهبي": "عرض سعر براده نبع المزن 2 ولف دهبى.pdf",
    "باقة برادة نبع المزن - 4 صنابير - أسود": "عرض سعر براده نبع المزن 4ولف اسود.pdf",
    "باقة برادة نبع المزن - 3 صنابير - أبيض": "عرض سعر براده نبع المزن ابيض.pdf",
    "باقة برادة نبع المزن - 3 صنابير - أسود": "عرض سعر براده نبع المزن اسود.pdf",
    "باقة برادة نبع المزن - 3 صنابير - ذهبي": "عر ض سعر براده نبع المزن دهبى.pdf",
    "باقة نبع المزن مدمجة - برادة مياه 3 صنابير وبرادة طعام - أبيض": "عرض سعر براده نبع المزن مدمجه ابيض.pdf",
    "باقة نبع المزن مدمجة - برادة مياه 3 صنابير وبرادة طعام - أسود": "عرض سعر براده نبع المزن مدمجه اسود.pdf",
    "باقة نبع المزن مدمجة - برادة مياه 3 صنابير وبرادة طعام - ذهبي": "عرض سعر براده نبع المزن مدمجه دهبى.pdf",
    "باقة برادة سقيا الخير - 2 صنبور - أبيض": "عرض سعر براده سقيى الخير 2ولف ابيض.pdf",
    "باقة برادة سقيا الخير - 2 صنبور - أسود": "عرض سعر براده سقيى الخير 2ولف اسود.pdf",
    "باقة برادة سقيا الخير - 2 صنبور - ذهبي": None,
    "باقة برادة سقيا الخير - 3 صنابير - أبيض": "عرض سعر براده سقيى الخير ابيض.pdf",
    "باقة برادة سقيا الخير - 3 صنابير - أسود": "عرض سعر براده سقيى الخير اسود.pdf",
    "باقة برادة سقيا الخير - 3 صنابير - ذهبي": "عرض سعر براده سقيى الخير دهبى.pdf",
    "باقة سقيا الخير مدمجة - برادتا مياه 3 صنابير وبرادة طعام - أبيض": "عرض سعر براده سقيى الخير مدمجه ابيض.pdf",
    "باقة سقيا الخير مدمجة - برادتا مياه 3 صنابير وبرادة طعام - أسود": "عرض سعر براده سقيى الخير مدمجه اسود.pdf",
    "باقة سقيا الخير مدمجة - برادتا مياه 3 صنابير وبرادة طعام - ذهبي": "عرض سعر براده سقيى الخير مدمجه دهبى.pdf",
    "باقة سقيا الخير مدمجة - برادة مياه 3 صنابير وبرادة طعام - أبيض": "عرض سعر براده سقيى الخير مدمجه ابيض.pdf",
    "باقة سقيا الخير مدمجة - برادة مياه 3 صنابير وبرادة طعام - أسود": "عرض سعر براده سقيى الخير مدمجه اسود.pdf",
    "باقة سقيا الخير مدمجة - برادة مياه 3 صنابير وبرادة طعام - ذهبي": "عرض سعر براده سقيى الخير مدمجه دهبى.pdf",
    "باقة برادة حفظ الطعام - غطاء سقيا الخير": "عرض سعر براده حفظ النعمه بكفر سقيى الخير.pdf",
    "باقة برادة حفظ الطعام - غطاء نبع المزن": "عرض سعر براده حفظ النعمه بكفر نبع المزن.pdf",
    "باقة برادة سقيا الخير ستانلس ستيل - 2 صنبور": "عرض سعر لبراده 2ولف استيلس.pdf",
    "باقة برادة سقيا الخير ستانلس ستيل - 3 صنابير": "عرض سعر لبراده 3ولف استيلس.pdf",
    "باقة برادة سقيا الخير ستانلس ستيل - 4 صنابير": "عرض سعر لبراده 4ولف استيلس.pdf",
    "باقة برادة مياه - 6 صنابير - أبيض": "عرض سعر براده 6 ولف ابيض.pdf",
    "باقة نظام فلترة مركزي - موديل 1054": "عرض سعر سستم مركزى.pdf",
    "باقة نظام فلترة ميني - مقاس 10×35": "عرض سعر سستم منى.pdf",
    "باقة فلتر جامبو ثنائي - مقاس 20": "عرض سعر جامبوا ثنائى.pdf",
    "باقة جهاز تنقية RO Technology - سعة 100 GPD": "عرض سعر RO TECHNOLOGHY.pdf",
    "باقة جهاز تنقية RO VIB - سعة 100 GPD": "عرض سعر RO VIB.pdf",
    "باقة موزع مياه RO - 3 صنابير": "عرض سعر TAP WATER 3DISPENSER.pdf",
    "فلتر دش Future Life": "عرض سعر شاور فيوتشر لايف.pdf",
    "باب خلفي جرار لبرادة مدمجة": "عرض سعر باب جرار لبراده مدمجه.pdf",
    "باب خلفي مفصلي لبرادة 3 صنابير": "عرض سعر باب مفصلى براده 3ولف.pdf",
    "باب خلفي مفصلي لبرادة 4 صنابير": "عرض سعر باب مفصلى براده 4ولف.pdf",
    "باب خلفي مفصلي لبرادة خاصة (Special)": "عرض سعر لباب مفصلى براده اسبشيال.pdf",
    "لوح خلفي ثابت لبرادة مدمجة": "عرض سعر لقطعه ثابته براده مدمجه.pdf",
    "لوح خلفي ثابت لبرادة 4 صنابير": "عرض سعر قطعه ثابته لبراده 4ولف.pdf",
    "لوح كلادينج ثابت لبرادة 3 صنابير": "عرض سعر قطعه كلادينج ثابته لبراده 3ولف.pdf",
}


def same_name(name: str) -> str:
    return "".join(name.split()).lower()


# PDF item names whose words come out in another order than the Daftra product's name
DAFTRA_NAME_ALIASES = {"tap 3 water dispenser with ro": "3 tap water dispenser with ro"}


def daftra_key(name: str) -> str:
    """Looser than same_name: also drops punctuation, since pdfplumber sometimes reorders a
    name's parentheses around mixed Arabic/English text (e.g. "(20 (AL" for "20 (AL)")."""
    return re.sub(r"[^a-z0-9؀-ۿ]", "", name.lower())


def money(value) -> Decimal:
    cleaned = str(value).replace(",", "").strip()
    return Decimal(cleaned or "0").quantize(Decimal("0.01"))


def guess_color(name: str) -> str:
    return next((word for word in COLOR_WORDS if word in name), "")


def cell(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def col_index(header: list, keyword: str) -> int | None:
    return next((i for i, c in enumerate(header) if keyword in cell(c)), None)


def parse_pdf(path: Path) -> list[dict]:
    """Returns the item lines of one quotation PDF: name, quantity, unit price (tax-exclusive)."""
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                header = table[0]
                item_i, price_i, qty_i = col_index(header, "Item"), col_index(header, "Price"), col_index(header, "Qty")
                if item_i is None or price_i is None or qty_i is None:
                    continue
                for row in table[1:]:
                    if row is None or item_i >= len(row):
                        continue
                    name, price, qty = cell(row[item_i]), cell(row[price_i]), cell(row[qty_i])
                    if not name or not re.fullmatch(r"[\d,]+(\.\d+)?", price):
                        continue
                    lines.append({"name": name, "quantity": int(qty) if qty.isdigit() else 1, "unit_price": money(price)})
    return lines


def invoice_usage(pages: int = 6) -> Counter:
    """How often each Daftra product id appears on the most recent invoices (100 per page).

    Daftra has many products under the same name, all active; the one the business actually
    invoices is the one to link, so a package's invoice uses the same product (and stock) as by hand.
    """
    usage = Counter()
    try:
        for page in range(1, pages + 1):
            rows = daftra_api.get("invoices.json", {"recursive": 1, "limit": 100, "page": page}).get("data", [])
            for row in rows:
                usage.update(str(item.get("product_id")) for item in row.get("InvoiceItem") or [])
            if len(rows) < 100:
                break
    except daftra_api.DaftraError as error:
        print(f"Could not read invoice history from Daftra ({error}); same-name products are picked by order.")
    return usage


def load_daftra_products(path: str, usage: Counter) -> tuple[dict[str, dict], dict[str, dict]]:
    """Daftra's products.json, keyed by normalized name and, more loosely, by daftra_key.
    On a name clash, prefers an active row, then the one used on the most recent invoices."""
    with open(path, encoding="utf-8-sig") as f:
        rows = [row["Product"] for row in json.load(f)["data"]]
    by_name: dict[str, dict] = {}
    by_loose: dict[str, dict] = {}
    rank = lambda entry: (entry["_active"], usage[str(entry.get("id"))])
    for row in rows:
        name = " ".join((row.get("name") or "").split())
        if not name:
            continue
        active = row.get("status") == "0" and row.get("deactivate") == "0"
        entry = {**row, "_name": name, "_active": active}
        for table, key in ((by_name, same_name(name)), (by_loose, daftra_key(name))):
            if key not in table or rank(entry) > rank(table[key]):
                table[key] = entry
    return by_name, by_loose


def daftra_fields(row: dict | None) -> dict:
    if row is None:
        return {}
    categories = row.get("ProductCategory") or []
    return {
        "daftra_id": int(row["id"]) if row.get("id") else None,
        "product_code": row.get("product_code") or None,
        "barcode": row.get("barcode") or None,
        "buy_price": money(row["buy_price"]) if row.get("buy_price") else None,
        "stock_balance": int(float(row["stock_balance"])) if row.get("stock_balance") not in (None, "") else None,
        "category": categories[0]["name"] if categories else None,
        "brand": row.get("brand") or None,
        # Sent as the line's description on the invoices an approved request creates
        "description": (row.get("description") or "").replace("\r\n", "\n").strip(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--proposals-dir", default="../../Proposals")
    parser.add_argument("--products-json", default="../../products.json")
    parser.add_argument("--dry-run", action="store_true", help="Parse and match everything, print the report, change nothing")
    args = parser.parse_args()

    proposals_dir = Path(args.proposals_dir)
    daftra, daftra_loose = load_daftra_products(args.products_json, invoice_usage())

    # Parse every PDF this mapping actually uses, once each (several package names reuse the same PDF)
    pdf_items: dict[str, list[dict]] = {}
    missing_pdfs, missing_in_daftra = [], set()
    for package_name, pdf_name in PACKAGE_PDFS.items():
        if pdf_name is None:
            continue
        if pdf_name not in pdf_items:
            path = proposals_dir / pdf_name
            if not path.exists():
                missing_pdfs.append((package_name, pdf_name))
                continue
            pdf_items[pdf_name] = parse_pdf(path)

    # Build one product per distinct item name across all parsed PDFs
    products_by_key: dict[str, dict] = {}
    for items in pdf_items.values():
        for item in items:
            key = same_name(item["name"])
            if key not in products_by_key:
                daftra_name = DAFTRA_NAME_ALIASES.get(item["name"], item["name"])
                match = daftra.get(same_name(daftra_name)) or daftra_loose.get(daftra_key(daftra_name))
                products_by_key[key] = {"name": item["name"], "unit_price": item["unit_price"], "daftra": match}
                if match is None:
                    missing_in_daftra.add(item["name"])

    print(f"{len(PACKAGE_PDFS)} package names, {len(pdf_items)} distinct PDFs parsed, "
          f"{len(products_by_key)} distinct products found")
    if missing_pdfs:
        print("\nPackage names whose PDF is missing on disk:")
        for package_name, pdf_name in missing_pdfs:
            print(f"  {package_name} -> {pdf_name}")
    no_pdf = [name for name, pdf in PACKAGE_PDFS.items() if pdf is None]
    if no_pdf:
        print("\nPackage names with no quotation yet (created empty):")
        for name in no_pdf:
            print(f"  {name}")
    if missing_in_daftra:
        print(f"\n{len(missing_in_daftra)} item(s) from the PDFs not found in products.json by name "
              f"(added with PDF name/price only, no Daftra fields):")
        for name in sorted(missing_in_daftra):
            print(f"  {name}")

    if args.dry_run:
        print("\n--dry-run: no database changes made.")
        return

    run_migrations()
    with SessionLocal() as db:
        db.query(PackageItem).delete()
        db.query(Package).delete()
        db.query(Product).delete()
        db.flush()

        products = {}
        for key, info in products_by_key.items():
            product = Product(
                # The PDFs' "Price" column equals their "Total With VAT" column, so it's tax-inclusive
                name=info["name"], unit_price=info["unit_price"],
                price_includes_tax=True, tax_rate=DEFAULT_TAX_RATE, is_active=True,
                **daftra_fields(info["daftra"]),
            )
            db.add(product)
            products[key] = product
        db.flush()  # products need their ids before package_items can reference them

        for code_index, (package_name, pdf_name) in enumerate(PACKAGE_PDFS.items(), start=1):
            package = Package(
                code=f"FLP-{code_index:03d}", name=package_name, color=guess_color(package_name), is_active=True,
            )
            db.add(package)
            db.flush()
            items = pdf_items.get(pdf_name, []) if pdf_name else []
            set_items(package, [
                {"product": products[same_name(item["name"])], "quantity": item["quantity"],
                 "unit_price": item["unit_price"], "price_includes_tax": True, "discount": Decimal("0")}
                for item in items
            ])

        db.commit()
        print(f"\nCatalog replaced: {len(products)} products, {len(PACKAGE_PDFS)} packages")


if __name__ == "__main__":
    main()
