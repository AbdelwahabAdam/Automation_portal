"""Fill products, packages and their links from the quotation lines workbook.

Usage: python -m app.import_products <workbook.xlsx> [--sheet "sheet name"]

Reads the sheet whose rows are quotation lines (one row per product inside a package).
Safe to run again: products and packages are matched by name and code and updated,
and anything added by hand in the portal is left alone.
"""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal

from openpyxl import load_workbook
from sqlalchemy import select

from ...modules.catalog.service import line_total, set_items
from ...core.database import SessionLocal, run_migrations
from ...modules.models import Package, Product

# Column headers in the workbook
PACKAGE_CODE = "مرجع النسخة"
PACKAGE_NAME = "اسم المنتج الكامل"
COLOR = "اللون"
PRODUCT_NAME = "اسم البند في المصدر"
PRODUCT_NAME_AR = "معنى البند"
DESCRIPTION = "وصف البند بالمصدر"
QUANTITY = "الكمية"
UNIT_PRICE = "سعر الوحدة بالمصدر (درهم)"
PRICE_BASIS = "أساس سعر الوحدة"
INCLUDES_TAX = "شامل الضريبة"
DISCOUNT = "خصم داخل البند (درهم)"
TAX_RATE = "نسبة الضريبة"
SOURCE_TOTAL = "إجمالي البند بالمصدر (درهم)"
ORDER = "ترتيب البند داخل العرض"
REQUIRED = [PACKAGE_CODE, PACKAGE_NAME, PRODUCT_NAME, QUANTITY, UNIT_PRICE, PRICE_BASIS, DISCOUNT, TAX_RATE]


def same_product(name: str) -> str:
    """Names that differ only in spacing or letter case are one product ("SAND SIZE 04- 08" / "SAND SIZE 04-08")."""
    return "".join(name.split()).lower()


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def read_lines(path: str, sheet: str | None) -> list[dict]:
    workbook = load_workbook(path, data_only=True)
    candidates = []
    for name in [sheet] if sheet else workbook.sheetnames:
        rows = list(workbook[name].iter_rows(values_only=True))
        header = [str(cell).strip() if cell is not None else "" for cell in rows[0]] if rows else []
        if all(column in header for column in REQUIRED):
            candidates.append((COLOR in header, header, rows[1:]))
    if not candidates:
        raise SystemExit(f"No sheet in {path} has the columns: {', '.join(REQUIRED)}")
    # Several sheets can hold the same lines; the one that also gives each package's colour wins
    _, header, rows = max(candidates, key=lambda candidate: candidate[0])
    return [dict(zip(header, row)) for row in rows if row[header.index(PACKAGE_CODE)]]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workbook")
    parser.add_argument("--sheet")
    args = parser.parse_args()

    lines = read_lines(args.workbook, args.sheet)
    run_migrations()

    # One product per distinct item name; its default price is the one most packages use
    by_product = defaultdict(list)
    for line in lines:
        by_product[same_product(str(line[PRODUCT_NAME]))].append(line)

    with SessionLocal() as db:
        existing = {same_product(p.name): p for p in db.scalars(select(Product))}
        products = {}
        for key, group in by_product.items():
            names = Counter(" ".join(str(line[PRODUCT_NAME]).split()) for line in group)
            price, includes_tax = Counter(
                (money(line[UNIT_PRICE]), line[PRICE_BASIS] == INCLUDES_TAX) for line in group
            ).most_common(1)[0][0]
            # The commonest spelling, and the tidier one when two are as common
            product = existing.get(key) or Product(name=min(names, key=lambda name: (-names[name], len(name))))
            product.name_ar = str(group[0].get(PRODUCT_NAME_AR) or "").strip()
            product.description = next((str(line[DESCRIPTION]).strip() for line in group if line.get(DESCRIPTION)), "")
            product.unit_price = price
            product.price_includes_tax = includes_tax
            product.tax_rate = Decimal(str(group[0][TAX_RATE]))
            db.add(product)
            products[key] = product

        by_package = defaultdict(list)
        for line in lines:
            by_package[str(line[PACKAGE_CODE]).strip()].append(line)
        known = {p.code: p for p in db.scalars(select(Package)) if p.code}
        mismatches = []
        for code, group in by_package.items():
            group.sort(key=lambda line: line.get(ORDER) or 0)
            package = known.get(code) or Package(code=code)
            package.name = " ".join(str(group[0][PACKAGE_NAME]).split())
            package.color = str(group[0].get(COLOR) or "").strip()
            # A product listed twice in one quotation becomes one line with the quantities added
            merged = {}
            for line in group:
                key = same_product(str(line[PRODUCT_NAME]))
                if key in merged:
                    merged[key]["quantity"] += int(line[QUANTITY])
                    merged[key]["discount"] += money(line[DISCOUNT])
                else:
                    merged[key] = {
                        "product": products[key], "quantity": int(line[QUANTITY]),
                        "unit_price": money(line[UNIT_PRICE]),
                        "price_includes_tax": line[PRICE_BASIS] == INCLUDES_TAX, "discount": money(line[DISCOUNT]),
                    }
            db.add(package)
            db.flush()  # products and the package need their ids before lines are matched to existing ones
            set_items(package, list(merged.values()))
            source_total = sum(money(line.get(SOURCE_TOTAL)) for line in group)
            ours = sum(line_total(item) for item in package.items)
            if SOURCE_TOTAL in group[0] and abs(ours - source_total) > Decimal("0.05"):
                mismatches.append(f"  {code} {package.name}: workbook {source_total}, calculated {ours}")
        db.commit()
        print(f"{len(lines)} lines -> {len(products)} products, {len(by_package)} packages, "
              f"{sum(len(p.items) for p in db.scalars(select(Package)))} links in the database")
        if mismatches:
            print("Totals that differ from the workbook:\n" + "\n".join(mismatches))


if __name__ == "__main__":
    main()
