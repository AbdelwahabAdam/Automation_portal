"""The installation work order (أمر الشغل) of a new sale: in Daftra, linked to its invoice, with
its custom fields filled in, and as a PDF the portal draws."""

import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import printouts
from ...integrations import daftra
from ...core.config import settings
from ...integrations.daftra import DaftraError
from ..form_engine import INSCRIPTIONS, NO_INSCRIPTION, package_colors, package_quantity
from ..catalog import Product
from ...core.text import UAE, day_month_year, display_name, squash
from .common import WORK_ORDER_ATTACHMENT_FIELD, attach_pdf, marker

# The work order's custom fields in our Daftra account (its form «نموذج أمر تشغيل ومتابعة عقد»), worked
# out from the values staff put in them: there is no API listing their labels
WORK_ORDER_FIELDS = {
    "installation_accessories": "field_8",   # ملحقات التركيب
    "product_image": "field_30",             # صورة المنتج (رفع صورة) — required, a file id
    "available_colors": "field_32",          # الألوان المتاحة
    "cover_back": "field_33",                # ظهر الكفر
    "base_color": "field_36",                # لون القاعده
    "location": "field_37",                  # اللوكيشن
    "design_version": "field_38",            # تصميم قديم & جديد
    "sales_person": "field_39",              # اسم الموظف (the salesperson)
    "cooler_color": "field_44",              # لون البراده
    "w_direction": "field_45",               # اتجاه الدبليو
    "front_design": "field_46",              # تصميم القطعه الاماميه
    "inscription": "field_47",               # الآية القرآنية المطبوعة
    "plate_color": "field_49",               # لون اللوحه
    # التمديدات الزيادة: found by reading every work order on the account — five of 3,088 have it
    # filled, and they hold «تمديد الكهرباء» and «تمديد المياه» (work orders 358, 359, 370, 1942, 2112).
    # The form stopped asking for them, so only a request from before that still fills this in.
    "extensions": "field_34",                # التمديدات الزياده ان وجدت
}
# Daftra replaces the whole custom form on every save, so a field left out of the body is emptied,
# not kept. Every field is therefore always sent, blank ones included.
CONTAINS_CUSTOM_DATA = {"CONTAINE_CUSTOM_DATA": "1"}  # Daftra's own spelling; required on every save
# Colours as staff write them in those fields
COLOR_TEXT = {"أبيض": "اللون الابيض", "أسود": "اللون الاسود", "ذهبي": "اللون الدهبي"}
BASE_TEXT = {"أسود": "لون القاعده ( الاسود)", "أبيض": "لون القاعده ( الابيض )",
             "الرصاصي": "لون القاعده ( الرصاصي )"}
# Several of the custom fields are lists in Daftra, one choice each. A save in Daftra's own screens
# empties a value that is not exactly one of the list's entries, so these are the entries to the
# letter, taken from the values saved on the account. The trailing spaces are the list's own.
COOLER_ENTRIES = {"أبيض": "اللون الابيض ", "أسود": "اللون الاسود ", "ذهبي": "اللون الدهبي "}
STAINLESS_ENTRY = "ستانلس ستيل"
WHITE, BLACK, GOLD, WOOD, AINAWI = "اللون الابيض", "اللون الاسود", "اللون الدهبي", "اللون الخشبي", "اللون العيناوي"
# لون اللوحه of each cover colour on the form. No rule gives it: «الابيض» alone has a wooden plate on
# سقيا الخير مدمجه, and «الاسود مقاس طبيعي» a golden one. Those staff have used are as they used them.
PLATE_ENTRIES = {
    "الابيض": WOOD, "الاسود": GOLD, "الابيض * الابيض": WHITE, "الابيض * الذهبى": GOLD,
    "الابيض * خشابي مقاس طبيعي": WOOD, "الاسود مقاس طبيعي": GOLD, "الابيض * ابيض مقاس طبيعي": WHITE,
    "الابيض * ذهبي مقاس طبيعي": GOLD, "الاسود * الخشبي مقاس طبيعي": WOOD, "الاسود * الاسود مقاس طبيعي": BLACK,
    "البني والأسود": BLACK, "الأبيض والذهبي المطفي": GOLD, "الرصاصي والأبيض": WHITE, "البني والأبيض": WHITE,
    "الرصاصي والأسود": BLACK, "الأبيض والذهبي لامع": GOLD, "الأبيض والعيناوي": AINAWI, "الأبيض * الابيض": WHITE,
    "الرصاصي* الذهبي مط": GOLD, "البني * الذهبي مط": GOLD, "الأبيض *  اللون الاسود": BLACK, "الرصاصي* الخشبي": WOOD,
    "6 ولف ابيض": WHITE,
}
# The list writes a verse with its code: «001 - …», and from 100 on «104- …»
INSCRIPTION_ENTRIES = {text: f"{code}- {text}" if int(code) >= 100 else f"{code} - {text}" for code, text in INSCRIPTIONS}


def package_lines(data: dict) -> list[dict]:
    """One line per package (and per standalone product): the one carrying its details."""
    lines = data.get("order_lines") or []
    return [line for i, line in enumerate(lines)
            if not line.get("group_id") or line["group_id"] not in {l.get("group_id") for l in lines[:i]}]


def product_image_id(data: dict, db: Session) -> str:
    """The file id for صورة المنتج: the image of the first line's product, which is what the work
    order is about. Falls back to the account's stand-in image when that product has none."""
    first = next((line for line in (data.get("order_lines") or [])
                  if str(line.get("product_id", "")).isdigit()), None)
    if first is not None:
        product = db.get(Product, int(first["product_id"]))
        if product is not None and product.file_id:
            return str(product.file_id)
    return str(settings.daftra_work_order_image_id)


def work_order_values(request, db: Session) -> dict:
    """The custom field values for the work order, from the request. A field the request has
    nothing for is left out. Several packages' values are joined with « / »."""
    data = request.data
    owners = package_lines(data)

    def joined(make) -> str:
        values = [make(line.get("details") or {}, line) for line in owners]
        return " / ".join(dict.fromkeys(str(v).strip() for v in values if v and str(v).strip()))

    def inscription(details, _):
        text = str(details.get("inscription") or "").strip()
        return text if text and text not in NO_INSCRIPTION else ""

    def available_colors(details, line):
        # The cover colour as staff write it here, e.g. «سقيا الخير - اللون الابيض * خشابي مقاس طبيعي»
        written = dict(package_colors(line.get("group_name") or line.get("name"))).get(details.get("cover_color"))
        if written:
            return written
        count = package_quantity(line)
        parts = [line.get("group_name") or line.get("name"),
                 f"الكمية {count}" if count > 1 else "",
                 f"لون البرادة {details['cooler_color']}" if details.get("cooler_color") else "",
                 f"لون الغطاء {details['cover_color']}" if details.get("cover_color") else ""]
        return " – ".join(p for p in parts if p)

    def cooler_color(details, _):
        value = details.get("cooler_color")
        return COLOR_TEXT.get(value) or (f"اللون {value}" if value else "")

    values = {
        "installation_accessories": joined(lambda d, _: d.get("installation_accessories")),
        "extensions": joined(lambda d, _: "، ".join(d.get("extensions") or [])),
        "available_colors": joined(available_colors),
        "cover_back": joined(lambda d, _: d.get("cover_back")),
        "base_color": joined(lambda d, _: BASE_TEXT.get(d.get("base_color"), d.get("base_color"))),
        "location": data.get("location_url") or "",
        "design_version": joined(lambda d, _: d.get("design_version")),
        "sales_person": display_name(request.created_by),
        "cooler_color": joined(cooler_color),
        "w_direction": joined(lambda d, _: d.get("w_direction")),
        "front_design": joined(lambda d, _: d.get("front_design")),
        "inscription": joined(inscription),
        "plate_color": joined(lambda d, _: COLOR_TEXT.get(d.get("cover_color")) or (f"اللون {d['cover_color']}" if d.get("cover_color") else "")),
        "product_image": product_image_id(data, db),
    }
    return values


def listed_values(data: dict, values: dict) -> dict:
    """What goes in the fields that are lists in Daftra, in place of the readable values the PDF
    prints. A list takes one entry, so it is the order's first package (or, with none, its first
    line); the rest stay on the PDF. values: work_order_values, for what is the same either way."""
    owners = package_lines(data)
    line = next((owner for owner in owners if owner.get("group_id")), owners[0] if owners else {})
    details = line.get("details") or {}
    name = line.get("group_name") or line.get("name") or ""
    written = dict(package_colors(name)).get(details.get("cover_color"))
    cooler = COOLER_ENTRIES.get(details.get("cooler_color")) or (STAINLESS_ENTRY if "ستانلس" in name else "")
    return {
        # A colour the form's list gives is the entry; a package it has none for keeps the words
        "available_colors": written or values.get("available_colors", "").split(" / ")[0],
        "cooler_color": cooler,
        "plate_color": PLATE_ENTRIES.get(details.get("cover_color"), ""),
        # A verse typed under «أخرى» is on no list; the PDF still carries it
        "inscription": INSCRIPTION_ENTRIES.get(str(details.get("inscription") or "").strip(), ""),
        "cover_back": details.get("cover_back") or "",
        "base_color": BASE_TEXT.get(details.get("base_color"), details.get("base_color") or ""),
        "design_version": details.get("design_version") or "",
        "w_direction": details.get("w_direction") or "",
        "front_design": details.get("front_design") or "",
    }


def work_order_custom_fields(request, db: Session) -> dict:
    """The values under the field ids Daftra knows them by."""
    values = work_order_values(request, db)
    values.update(listed_values(request.data, values))
    # Every field, blank ones included: Daftra empties any field the body leaves out
    return {WORK_ORDER_FIELDS[name]: value or "" for name, value in values.items()}


def set_work_order_fields(request, row: dict, db: Session) -> bool:
    """Writes the work order's custom fields, then reads them back to be sure. With a real file id in
    صورة المنتج Daftra answers 200, but it answered 500 for a while and the values saved anyway, so the
    read decides. A failure here does not stop the approval; the same details are in the description
    and the PDF."""
    fields = work_order_custom_fields(request, db)
    # An edit needs these again, as the work order has them, and a حالة someone has set in Daftra stays.
    # Without its number Daftra gives the work order the next one, and the portal's copy falls behind.
    work_order = {"number": row.get("number"), "title": row.get("title"),
                  "start_date": str(row.get("start_date") or "")[:10],
                  "delivery_date": str(row.get("delivery_date") or "")[:10]}
    if int(row.get("follow_up_status_id") or 0):
        work_order["follow_up_status_id"] = int(row["follow_up_status_id"])
    try:
        daftra.update_unconfirmed(f"work_orders/{request.daftra_work_order_id}.json", {
            "WorkOrder": work_order,
            "CustomModel": {**CONTAINS_CUSTOM_DATA, **fields},
        })
        # The values show up a moment after Daftra answers. Daftra reads an empty field back as the
        # text "None", so both it and "" count as blank.
        def blank_or(value) -> str:
            text = str(value) if value is not None else ""
            return "" if text in ("None", "") else text

        for attempt in range(4):
            time.sleep(1 + attempt)
            saved = daftra.read_v2("work_order", request.daftra_work_order_id).get("custom_data") or {}
            if all(blank_or(saved.get(key)) == blank_or(value) for key, value in fields.items()):
                return True
    except DaftraError:
        pass
    return False


def assign_sales_person(request, reviewer) -> bool:
    """Puts whoever sent the request under معلومات الموظفين المعينين on the work order, unless a
    retry finds them there already: Daftra keeps one row per call and the API cannot remove any.
    Those it is assigned to as well stay. A failure here does not stop the approval."""
    staff_id = request.created_by.daftra_staff_id
    try:
        if staff_id not in daftra.work_order_staff(request.daftra_work_order_id):
            daftra.assign_work_order(request.daftra_work_order_id, staff_id, reviewer.daftra_staff_id or staff_id)
    except DaftraError:
        return False
    return True


def work_order_title(data: dict, invoice: dict) -> str:
    """Like the ones staff write: what is installed, where, and the client code, e.g.
    «باقة برادة سقيا الخير - 3 صنابير - أسود أبوظبي منطقة العين 4092»."""
    lines = data.get("order_lines") or []
    names = list(dict.fromkeys(line.get("group_name") or line.get("name") or "" for line in lines))
    code = str((invoice.get("Client") or {}).get("client_number") or "").lstrip("0")
    parts = ["، ".join(name for name in names if name), data.get("emirate"), data.get("area"), code]
    return " ".join(str(part).strip() for part in parts if part and str(part).strip())[:250]


def work_order_rows(request, reviewer) -> list[str]:
    """What the technicians need, one line each, printed under «وصف» on the PDF the portal draws.

    Not the Daftra description any more — that holds ملاحظات خاصة للتصنيع alone — so the PDF is
    where the approving manager's name appears, Daftra's API having no field of its own for it.
    """
    data = request.data
    rows = []
    for line in package_lines(data):
        details = line.get("details") or {}
        count = package_quantity(line)
        rows.append(f"نوع الجهاز: {line.get('group_name') or line.get('name')}" + (f" — الكمية: {count}" if count > 1 else ""))
        colors = [f"لون البرادة: {details['cooler_color']}" if details.get("cooler_color") else "",
                  f"لون الغطاء: {details['cover_color']}" if details.get("cover_color") else "",
                  f"لون القاعدة: {details['base_color']}" if details.get("base_color") else ""]
        if any(colors):
            rows.append(" — ".join(c for c in colors if c))
        if details.get("design"):
            rows.append(f"التصميم: {details['design']}")
        build = [f"القطعة الأمامية: {details['front_design']}" if details.get("front_design") else "",
                 f"اتجاه الدبليو: {details['w_direction']}" if details.get("w_direction") else "",
                 f"ظهر الكفر: {details['cover_back']}" if details.get("cover_back") else "",
                 details.get("design_version") or ""]
        if any(build):
            rows.append(" — ".join(b for b in build if b))
        if details.get("installation_accessories"):
            rows.append(f"ملحقات التركيب: {details['installation_accessories']}")
        if details.get("extensions"):
            rows.append("التمديدات الزيادة: " + "، ".join(details["extensions"]))
        text = str(details.get("inscription") or "").strip()
        if text and text not in NO_INSCRIPTION:
            place = f" (مكان الكتابة: {details['inscription_place']})" if details.get("inscription_place") else ""
            rows.append(f"الكتابة: {text}{place}")
        if details.get("manufacturing_notes"):
            rows.append(f"ملاحظات التصنيع: {details['manufacturing_notes']}")
    if data.get("installation_days"):
        rows.append(f"مدة التركيب: {data['installation_days']} يومًا")
    address = "، ".join(str(data[k]) for k in ("emirate", "area", "street", "house") if data.get(k))
    rows += [
        f"العميل: {data.get('customer_name') or ''} — {data.get('phone') or ''}",
        f"العنوان: {address}" if address else "",
        f"اللوكيشن: {data['location_url']}" if data.get("location_url") else "",
        f"الإحداثيات: {data['coordinates']}" if data.get("coordinates") else "",
        f"رقم الفاتورة: {request.daftra_invoice_no}" if request.daftra_invoice_no else "",
        f"المسؤول: {display_name(reviewer)}",
        f"ملاحظات: {data['notes']}" if data.get("notes") else "",
    ]
    return [row for row in rows if row]


def manufacturing_notes(data: dict) -> str:
    """ملاحظات خاصة للتصنيع of every product in the order, one under the other.

    The same note written against two packages is printed once: it is a note for the floor, not a
    list of lines.
    """
    written = (str((line.get("details") or {}).get("manufacturing_notes") or "").strip()
               for line in package_lines(data))
    return "\n".join(dict.fromkeys(note for note in written if note))


def work_order_description(request) -> str:
    """ملاحظات خاصة للتصنيع alone, then the marker that finds the work order again on a retry.

    Nothing else goes here: the client is the work order's own, the location and the colours are
    its custom fields, the invoice is linked to it, its title carries the emirate, the area and
    the client's code, and the PDF the portal attaches carries the rest for the floor.
    """
    notes = manufacturing_notes(request.data)
    return "\n".join(([notes] if notes else []) + [marker(request)])


def find_work_order(request) -> int | None:
    rows = daftra.get("work_orders.json", {"client_id": request.daftra_client_id, "status": -1, "limit": 100}).get("data", [])
    return next((int(row["WorkOrder"]["id"]) for row in rows
                 if str(row["WorkOrder"].get("client_id")) == str(request.daftra_client_id)
                 and (row["WorkOrder"].get("description") or "").rstrip().endswith(marker(request))), None)


def ensure_work_order(request, invoice: dict, reviewer, db: Session):
    """The installation work order for the approving manager: it starts today and is due after the
    request's مدة التركيب. It is linked to the invoice, so the invoice shows it, and its PDF is attached."""
    data = request.data
    if request.daftra_work_order_id is None:
        request.save_document("work_order", find_work_order(request))
    if request.daftra_work_order_id is None:
        start = datetime.now(UAE).date()
        days = int(data.get("installation_days") or 20)
        request.save_document("work_order", daftra.create("work_orders.json", {"WorkOrder": {
            "title": work_order_title(data, invoice), "client_id": request.daftra_client_id,
            "start_date": start.isoformat(), "delivery_date": (start + timedelta(days=days)).isoformat(),
            "description": work_order_description(request),
        }}))
    row = daftra.get(f"work_orders/{request.daftra_work_order_id}.json").get("data", {}).get("WorkOrder", {})
    request.save_document("work_order", request.daftra_work_order_id, row.get("number") or "")
    if str(invoice.get("work_order_id") or "0") != str(request.daftra_work_order_id):
        daftra.post(f"invoices/assign_work_order/{request.daftra_invoice_id}.json",
                    {"Invoice": {"work_order_id": request.daftra_work_order_id}})
    fields_saved = set_work_order_fields(request, row, db)
    sales_assigned = assign_sales_person(request, reviewer)
    return save_work_order_pdf(request, row, invoice, reviewer, db), fields_saved, sales_assigned


def draw_work_order(request, row: dict, invoice: dict, reviewer, db: Session) -> bytes:
    """The work order PDF, drawn to match «نموذج أمر تشغيل ومتابعة عقد» as Daftra prints it:
    Daftra's own file is behind a staff login, which an API key cannot open.
    row: the work order as Daftra returns it, for its number, title and dates.

    Kept apart from saving it so app.redraw_work_orders can draw an old one again after the
    template changes, from the one template both of them use.
    """
    data = request.data
    start, delivery = str(row.get("start_date") or ""), str(row.get("delivery_date") or "")
    address = "، ".join(str(data[key]) for key in ("emirate", "area", "street", "house") if data.get(key))
    return printouts.work_order(
        number=request.daftra_work_order_no or "", title=row.get("title") or work_order_title(data, invoice),
        start=day_month_year(start), delivery=day_month_year(delivery),
        rows=work_order_rows(request, reviewer), values=work_order_values(request, db),
        client_name=squash(data.get("customer_name")), client_code=str(data.get("client_code") or ""),
        phone=str(data.get("phone") or ""), address=address,
        location_url=str(data.get("location_url") or ""), coordinates=str(data.get("coordinates") or ""),
        # Daftra holds the picture by a file id and gives no address for it, so the line is
        # left to fill in, as صورة المعاينة is on its own form
        product_image="", invoice_no=request.daftra_invoice_no or "",
        responsible=display_name(reviewer), sales_person=display_name(request.created_by),
    )


def save_work_order_pdf(request, row: dict, invoice: dict, reviewer, db: Session) -> bool:
    """Attaches the work order PDF once. A PDF that cannot be drawn does not stop the approval."""
    if any(a.field == WORK_ORDER_ATTACHMENT_FIELD for a in request.attachments):
        return True
    try:
        content = draw_work_order(request, row, invoice, reviewer, db)
    except printouts.PrintoutError:
        return False
    attach_pdf(request, WORK_ORDER_ATTACHMENT_FIELD, "أمر شغل", invoice, content, db)
    return True
