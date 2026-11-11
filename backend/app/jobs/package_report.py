"""Every package with the products inside it — one HTML page with each product's picture and description.

Usage: python -m app.jobs package_report [--out FILE] [--all] [--links] [--no-images]

Written to be read, not to be acted on: it is for checking by eye that each package holds the
products it should. One product per row, in the order the package puts them, with the picture the
work order would print, the description that goes on the quotation, the quantity and the price.

The picture is the one a product's `file_id` points at in Daftra — the same file id the work
order's صورة المنتج carries — so what the page shows is what a customer would see, not what the
product is called. Where the two disagree the row says so: «الصورة تنتمي لمنتج آخر في دفترة».

Options:
    --out FILE    where to write it (default: package_report.html)
    --all         inactive packages too, each marked «غير مفعّلة»
    --links       point at Daftra's own image links instead of embedding the pictures. Smaller
                  file, but the links are signed and stop working after a while
    --no-images   no pictures at all, and no call to Daftra: the database alone

Read-only: it reads our database and Daftra's product list, and writes the one file it is given.
"""

import argparse
import base64
import html
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..core.text import UAE
from ..integrations import daftra
from ..modules.models import Package, PackageItem
from .registry import job

IMAGE_TIMEOUT = 60
# What a thumbnail is worth embedding; a bigger one is linked instead, so the file stays openable
MAX_EMBED_BYTES = 3_000_000


def packages_of(db, include_inactive: bool = False) -> list[dict]:
    """Every package, its items in their own order, with the product behind each one."""
    query = (select(Package)
             .options(selectinload(Package.items).joinedload(PackageItem.product))
             .order_by(Package.code, Package.name))
    if not include_inactive:
        query = query.where(Package.is_active.is_(True))
    found = []
    for package in db.scalars(query):
        found.append({
            "id": package.id,
            "code": package.code or "",
            "name": package.name,
            "color": package.color or "",
            "is_active": package.is_active,
            "items": [{
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "price_includes_tax": item.price_includes_tax,
                "discount": item.discount,
                "sort_order": item.sort_order,
                "product": {
                    "id": item.product.id,
                    "sku": item.product.sku or "",
                    "daftra_id": item.product.daftra_id,
                    "file_id": item.product.file_id,
                    "name": item.product.name,
                    "name_ar": item.product.name_ar or "",
                    "description": item.product.description or "",
                    "open_price": item.product.open_price,
                    "unit_price": item.product.unit_price,
                    "is_active": item.product.is_active,
                    "category": item.product.category or "",
                    "brand": item.product.brand or "",
                },
            } for item in sorted(package.items, key=lambda i: (i.sort_order, i.product_id))],
        })
    return found


def image_index(raw_products: list[dict]) -> dict[int, dict]:
    """file id -> where its picture is and which Daftra product it belongs to."""
    index = {}
    for product in raw_products:
        for image in product.get("ProductImageS3") or []:
            if not str(image.get("id") or "").isdigit():
                continue
            index[int(image["id"])] = {
                "daftra_id": int(product["id"]),
                "daftra_name": (product.get("name") or "").strip(),
                "is_default": str(image.get("default") or "") == "1",
                "url": image.get("file_full_path") or "",
                "stored_name": image.get("file") or "",
            }
    return index


def notes(item: dict, image: dict | None, seen_images: dict[int, str]) -> list[str]:
    """What looks wrong about this row, in the words the office uses. Empty when nothing does."""
    product = item["product"]
    said = []
    if not product["is_active"]:
        said.append("منتج غير مفعّل")
    if not product["daftra_id"]:
        said.append("غير مرتبط بدفترة")
    if not product["file_id"]:
        said.append("لا توجد صورة")
    elif image is None:
        said.append("الصورة غير موجودة في دفترة")
    else:
        if product["daftra_id"] and image["daftra_id"] != product["daftra_id"]:
            said.append(f"الصورة تنتمي لمنتج آخر في دفترة: «{image['daftra_name']}»")
        elif not image["is_default"]:
            said.append("ليست الصورة الافتراضية للمنتج")
        other = seen_images.get(product["file_id"])
        if other and other != product["name"]:
            said.append(f"نفس صورة «{other}»")
    if not product["description"].strip():
        said.append("بدون وصف")
    return said


def fetch(url: str) -> tuple[bytes, str] | None:
    """The picture itself and its type, or None when it cannot be fetched."""
    try:
        with urllib.request.urlopen(url, timeout=IMAGE_TIMEOUT) as answer:
            return answer.read(), answer.headers.get("Content-Type") or "image/jpeg"
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def money(amount: Decimal) -> str:
    return f"{amount:,.2f}"


# ---------- the page ----------

STYLE = """
:root { --line: #E2E8F0; --ink: #0F172A; --muted: #64748B; --warn: #B4530A; --warn-bg: #FEF6EC;
        --bad: #B91C1C; --bad-bg: #FEF2F2; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; font-family: "Segoe UI", Tahoma, system-ui, sans-serif;
       color: var(--ink); background: #F8FAFC; line-height: 1.6; }
h1 { font-size: 24px; margin: 0 0 4px; }
.sub { color: var(--muted); margin: 0 0 24px; font-size: 14px; }
.summary { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 16px 20px;
           margin-bottom: 24px; }
.summary ul { margin: 8px 0 0; padding-inline-start: 20px; }
.pack { background: #fff; border: 1px solid var(--line); border-radius: 12px; margin-bottom: 20px;
        overflow: hidden; break-inside: avoid; }
.pack__head { padding: 14px 20px; border-bottom: 1px solid var(--line); display: flex;
              align-items: baseline; gap: 12px; flex-wrap: wrap; background: #F1F5F9; }
.pack__code { font-family: Consolas, monospace; color: var(--muted); font-size: 13px; }
.pack__name { font-size: 18px; font-weight: 600; margin: 0; }
.pack__meta { color: var(--muted); font-size: 13px; margin-inline-start: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 12px; text-align: start; vertical-align: top; border-top: 1px solid var(--line);
         font-size: 14px; }
th { background: #FBFCFE; color: var(--muted); font-weight: 600; font-size: 13px; border-top: 0; }
tr.flagged td { background: var(--warn-bg); }
tr.bad td { background: var(--bad-bg); }
.thumb { width: 104px; height: 104px; object-fit: contain; background: #fff; border: 1px solid var(--line);
         border-radius: 8px; display: block; }
.nothumb { width: 104px; height: 104px; display: grid; place-items: center; border: 1px dashed var(--line);
           border-radius: 8px; color: var(--muted); font-size: 12px; text-align: center; }
.name { font-weight: 600; unicode-bidi: isolate; }
.en { color: var(--muted); font-size: 13px; direction: ltr; text-align: start; unicode-bidi: isolate; }
.ids { color: var(--muted); font-size: 12px; font-family: Consolas, monospace; direction: ltr;
       unicode-bidi: isolate; }
.desc { color: #334154; font-size: 13px; white-space: pre-wrap; max-width: 46ch;
        unicode-bidi: isolate; }
.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.note { display: inline-block; background: var(--warn-bg); color: var(--warn); border: 1px solid #F3D9B8;
        border-radius: 999px; padding: 1px 10px; font-size: 12px; margin: 2px 0 0; }
.note--bad { background: var(--bad-bg); color: var(--bad); border-color: #F5C2C2; }
.off { background: #F1F5F9; color: var(--muted); border-radius: 999px; padding: 1px 10px; font-size: 12px; }
.empty { padding: 16px 20px; color: var(--muted); }
@media print { body { background: #fff; padding: 0; } .pack { break-inside: auto; } }
"""

HARD = ("منتج غير مفعّل", "لا توجد صورة", "غير مرتبط بدفترة")


def tally(flagged: list[tuple]) -> dict[str, int]:
    """How many rows carry each kind of note, the worst kind first — the summary at the top."""
    counted: dict[str, int] = {}
    for _, _, said in flagged:
        for note in said:
            # The two notes that name another product are counted as one kind, not one per name
            kind = note.split(":")[0] if note.startswith("الصورة تنتمي") else note
            kind = "صورة مكررة بين منتجين" if kind.startswith("نفس صورة") else kind
            counted[kind] = counted.get(kind, 0) + 1
    order = {note: place for place, note in enumerate(HARD)}
    return dict(sorted(counted.items(), key=lambda pair: (order.get(pair[0], len(HARD)), -pair[1])))


def render(packages: list[dict], images: dict[int, bytes | str], when: datetime, account: str) -> str:
    """The whole page, as one string."""
    out = [
        "<!doctype html>", '<html lang="ar" dir="rtl">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>الباقات ومحتواها</title>", f"<style>{STYLE}</style>", "</head>", "<body>",
        "<h1>الباقات ومحتواها</h1>",
        f'<p class="sub">{len(packages)} باقة — {html.escape(account)} — '
        f'{when.strftime("%Y-%m-%d %H:%M")} بتوقيت الإمارات</p>',
    ]

    flagged = [(package, item, said) for package in packages for item, said in package["notes"] if said]
    empty = [package for package in packages if not package["items"]]
    out.append('<div class="summary">')
    if not flagged and not empty:
        out.append("<strong>لا توجد ملاحظات.</strong> كل منتج داخل كل باقة له صورة ووصف، وصورته تنتمي إليه في دفترة.")
    else:
        out.append(f'<strong>{len(flagged)} صف يحتاج نظرة</strong>، في '
                   f'{len({package["id"] for package, _, _ in flagged})} باقة من {len(packages)}.')
        out.append("<ul>")
        for kind, count in tally(flagged).items():
            out.append(f'<li>{html.escape(kind)}: <span class="num">{count}</span> صف</li>')
        for package in empty:
            out.append(f'<li>{html.escape(package["name"])}: باقة فارغة، لا منتجات داخلها</li>')
        out.append("</ul>")
        out.append('<p class="sub" style="margin:8px 0 0">كل صف منها مظلّل في مكانه أسفل الصفحة، '
                   "وسببه مكتوب تحت اسم المنتج.</p>")
    out.append("</div>")

    for package in packages:
        out.append('<section class="pack">')
        out.append('<div class="pack__head">')
        if package["code"]:
            out.append(f'<span class="pack__code">{html.escape(package["code"])}</span>')
        out.append(f'<h2 class="pack__name">{html.escape(package["name"])}</h2>')
        if package["color"]:
            out.append(f'<span class="off">{html.escape(package["color"])}</span>')
        if not package["is_active"]:
            out.append('<span class="off">غير مفعّلة</span>')
        total = sum(
            (item["unit_price"] * item["quantity"] - item["discount"]) for item in package["items"]
        )
        out.append(f'<span class="pack__meta">{len(package["items"])} منتج — '
                   f'<span class="num">{money(total)}</span> د.إ</span>')
        out.append("</div>")

        if not package["items"]:
            out.append('<p class="empty">لا منتجات داخل هذه الباقة.</p>')
            out.append("</section>")
            continue

        out.append("<table><thead><tr><th>الصورة</th><th>المنتج</th><th>الوصف</th>"
                   "<th>الكمية</th><th>السعر</th></tr></thead><tbody>")
        for item, said in package["notes"]:
            product = item["product"]
            bad = any(note in HARD or note.startswith("الصورة تنتمي") for note in said)
            row = " class=\"bad\"" if bad else (" class=\"flagged\"" if said else "")
            out.append(f"<tr{row}>")

            picture = images.get(product["file_id"]) if product["file_id"] else None
            if isinstance(picture, bytes):
                source = "data:image/jpeg;base64," + base64.b64encode(picture).decode("ascii")
                out.append(f'<td><img class="thumb" src="{source}" alt=""></td>')
            elif isinstance(picture, str) and picture:
                out.append(f'<td><img class="thumb" src="{html.escape(picture, quote=True)}" alt=""></td>')
            else:
                out.append('<td><div class="nothumb">لا صورة</div></td>')

            out.append("<td>")
            out.append(f'<div class="name" dir="auto">{html.escape(product["name_ar"] or product["name"])}</div>')
            if product["name_ar"]:
                out.append(f'<div class="en">{html.escape(product["name"])}</div>')
            marks = " · ".join(part for part in (product["sku"], product["category"], product["brand"]) if part)
            if marks:
                out.append(f'<div class="en">{html.escape(marks)}</div>')
            out.append(f'<div class="ids">#{product["id"]}'
                       f' · daftra {product["daftra_id"] or "—"}'
                       f' · file {product["file_id"] or "—"}</div>')
            for note in said:
                hard = note in HARD or note.startswith("الصورة تنتمي")
                out.append(f'<div class="note{" note--bad" if hard else ""}">{html.escape(note)}</div>')
            out.append("</td>")

            out.append(f'<td class="desc" dir="auto">{html.escape(product["description"].strip()) or "—"}</td>')
            out.append(f'<td class="num">{item["quantity"]}</td>')
            if product["open_price"]:
                price = "حسب الطلب"
            else:
                price = money(item["unit_price"])
                if item["discount"]:
                    price += f' <span class="en">− {money(item["discount"])}</span>'
            out.append(f'<td class="num">{price}</td>')
            out.append("</tr>")
        out.append("</tbody></table></section>")

    out += ["</body>", "</html>"]
    return "\n".join(out)


@job("package_report", label="تقرير الباقات ومحتواها", recorded=False,
     about="One HTML page: every package, the products in it, their pictures and descriptions")
def _run(db, who):
    """This one is a command line only: `python -m app.jobs package_report …`."""
    raise SystemExit("Run it as: python -m app.jobs package_report [options]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="package_report.html", help="where to write the page")
    parser.add_argument("--all", action="store_true", help="inactive packages too")
    parser.add_argument("--links", action="store_true", help="link Daftra's images instead of embedding")
    parser.add_argument("--no-images", action="store_true", help="no pictures, and no call to Daftra")
    args = parser.parse_args()

    from ..core.database import SessionLocal

    with SessionLocal() as db:
        packages = packages_of(db, include_inactive=args.all)
    print(f"{len(packages)} package(s), {sum(len(p['items']) for p in packages)} line(s) in all.")

    index: dict[int, dict] = {}
    if not args.no_images:
        if settings.daftra_fake:
            print("DAFTRA_FAKE is on: the fake account has no pictures, so the page is written without them.")
        else:
            print(f"Reading the product list from Daftra ({settings.daftra_subdomain})…")
            index = image_index(daftra.all_records("products", "Product"))
            print(f"  {len(index)} image(s) in the account.")

    # The notes, in one pass, so «نفس صورة …» can name the row that used the picture first
    seen: dict[int, str] = {}
    for package in packages:
        package["notes"] = []
        for item in package["items"]:
            said = notes(item, index.get(item["product"]["file_id"] or 0), seen)
            package["notes"].append((item, said))
            if item["product"]["file_id"]:
                seen.setdefault(item["product"]["file_id"], item["product"]["name"])

    wanted = {item["product"]["file_id"] for package in packages for item in package["items"]
              if item["product"]["file_id"] and item["product"]["file_id"] in index}
    pictures: dict[int, bytes | str] = {}
    if wanted and args.links:
        pictures = {file_id: index[file_id]["url"] for file_id in wanted}
    elif wanted:
        print(f"Fetching {len(wanted)} picture(s)…")
        for number, file_id in enumerate(sorted(wanted), start=1):
            got = fetch(index[file_id]["url"])
            if got is None:
                print(f"  file {file_id} could not be fetched; the page will link to it instead")
                pictures[file_id] = index[file_id]["url"]
            elif len(got[0]) > MAX_EMBED_BYTES:
                pictures[file_id] = index[file_id]["url"]
            else:
                pictures[file_id] = got[0]
            if number % 10 == 0:
                print(f"  {number} of {len(wanted)}…")

    page = render(packages, pictures, datetime.now(UAE), settings.daftra_subdomain or "—")
    out = Path(args.out)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"\n{out.resolve()}  ({len(page.encode('utf-8')) / 1_000_000:.1f} MB)")

    flagged = [(package, item, said) for package in packages for item, said in package["notes"] if said]
    if not flagged:
        print("No notes: every product in every package has a picture, a description, and its own image.")
    else:
        print(f"\n{len(flagged)} row(s) to look at:")
        for package, item, said in flagged:
            name = item["product"]["name_ar"] or item["product"]["name"]
            print(f"  {package['name']} — {name}: {'، '.join(said)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
