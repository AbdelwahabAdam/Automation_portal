"""Creating in Daftra what an approved request stands for:

- طلب بيع لعميل جديد: the client when new, the invoice with its lines, and the receipt (سند قبض)
  for what the customer paid now;
- طلب تجديد عقد الصيانة السنوي: the existing client's category, the one-line renewal invoice, and
  its receipt;
- طلب تسديد مبلغ متبقي: a receipt on one of the client's invoices.

Each step keeps the id it got on the request before the next one starts. Approving again after a
failure therefore carries on from the step that failed. If an id was lost (e.g. the response never
arrived), the invoice is found again by its po_number and the payment by its notes, both
"PORTAL-<request id>", so neither is created twice.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import daftra, printouts
from .config import UPLOAD_DIR, settings
from .daftra import PAYMENT_METHOD_KEYS, DaftraError, NotFound, local_phone
from .forms import NO_INSCRIPTION, package_colors, package_quantity
from .models import Address, Attachment, Client, Product, Request, User
from .text import UAE, day_month_year, digits, display_name, squash

INVOICE_ATTACHMENT_FIELD = "daftra_invoice"
RECEIPT_ATTACHMENT_FIELD = "daftra_receipt"
WORK_ORDER_ATTACHMENT_FIELD = "daftra_work_order"
# The description of the renewal invoice's one line, as staff write it by hand (e.g. invoice 06263)
RENEWAL_DESCRIPTION = "تجديد عقد الصيانه لمده عام مع تبديل فلاتر كل ثلاث اشهر"
CENT = Decimal("0.01")
# Daftra rounds each line's tax on its own, so a total can be off by a little
TOTAL_TOLERANCE = Decimal("0.05")


class SyncError(Exception):
    """Why the Daftra documents could not be created, in words the manager can act on.
    from_daftra says whether Daftra itself refused or failed, rather than our own checks."""

    def __init__(self, message: str, from_daftra: bool = False):
        super().__init__(message)
        self.from_daftra = from_daftra


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def sync(request: Request, db: Session, reviewer: User) -> dict:
    """Creates in Daftra whatever the approved request needs that does not exist yet. Returns a
    summary for the audit log; raises SyncError, leaving on the request the ids of what was created.
    The approving reviewer is the receipt's المستلم."""
    summary = SYNCS[request.form_type](request, db, reviewer)
    request.daftra_error = None
    request.daftra_synced_at = datetime.now(timezone.utc)
    return summary


def sync_new_sale(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    items = invoice_items(data, db)
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    wants_work_order = data.get("create_work_order") == "نعم"
    try:
        if request.daftra_client_id is None:
            request.daftra_client_id = client_id(data, db)
        set_client_category(request)
        invoice = ensure_invoice(request, items, staff_id)
        summary = finish(request, invoice, paid, method, reviewer, db)
        if wants_work_order:
            summary["work_order_pdf_saved"], summary["work_order_fields_saved"] = ensure_work_order(
                request, invoice, reviewer, db)
            summary["daftra_work_order_no"] = request.daftra_work_order_no
        return summary
    except DaftraError as error:
        raise daftra_failed(error) from error


def sync_contract_renewal(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    item = {
        "product_id": settings.daftra_renewal_product_id, "item": "exchange contract", "description": RENEWAL_DESCRIPTION,
        "unit_price": float(money(data.get("subtotal_amount"))), "quantity": 1,
        "tax1": settings.daftra_tax_id, "store_id": settings.daftra_store_id,
    }
    try:
        if request.daftra_client_id is None:
            found = existing_client_id(data, db)
            if found is None:
                raise SyncError(f"لا يوجد في دفترة عميل بالرقم {local_phone(data.get('phone'))} أو الكود "
                                f"«{data.get('client_code') or '—'}». التجديد لعميل موجود فقط؛ أعد الطلب للموظف ليصحح بيانات العميل.")
            request.daftra_client_id = found
        set_client_category(request)
        invoice = ensure_invoice(request, [item], staff_id)
        return finish(request, invoice, paid, method, reviewer, db)
    except DaftraError as error:
        raise daftra_failed(error) from error


def sync_maintenance(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    items = invoice_items(data, db)
    # The general «service» item says what was done
    for item in items:
        if item["product_id"] == settings.daftra_inscription_product_id and data.get("service_description"):
            item["description"] = data["service_description"]
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    notes = "\n".join(part for part in (
        "الأجهزة: " + "، ".join(data.get("devices") or []) if data.get("devices") else "",
        f"الخدمة: {data['service']}" if data.get("service") else "",
        f"تاريخ الزيارة: {day_month_year(str(data['visit_date']))}" if data.get("visit_date") else "",
    ) if part)
    try:
        if request.daftra_client_id is None:
            request.daftra_client_id = client_id(data, db)
        set_client_category(request)
        invoice = ensure_invoice(request, items, staff_id, notes=notes)
        return finish(request, invoice, paid, method, reviewer, db)
    except DaftraError as error:
        raise daftra_failed(error) from error


def sync_balance_payment(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    paid, method = payment_inputs(data)
    try:
        request.daftra_invoice_id = int(data["invoice"])
        try:
            invoice = get_invoice(request.daftra_invoice_id)
        except NotFound:
            raise SyncError(f"الفاتورة {data.get('invoice_name') or data['invoice']} لم تعد موجودة في دفترة. "
                            "أعد الطلب للموظف ليختار الفاتورة الصحيحة.")
        request.daftra_client_id = int(invoice["client_id"])
        request.daftra_invoice_no = invoice.get("no")
        unpaid = money(invoice.get("summary_unpaid"))
        if request.daftra_payment_id is None and not payment_of(request, invoice) and paid > unpaid + TOTAL_TOLERANCE:
            raise SyncError(f"المبلغ المدفوع {paid} أكبر من المتبقي على الفاتورة {request.daftra_invoice_no} ({unpaid}). "
                            "أعد الطلب للموظف ليصحح المبلغ.")
        result = finish(request, invoice, paid, method, reviewer, db, invoice_pdf_after_payment=True)
    except DaftraError as error:
        raise daftra_failed(error) from error
    return result


def set_client_category(request: Request):
    """Gives the request's client the التصنيف picked on the form (a partial update: only the category)."""
    data = request.data
    if data.get("category"):
        daftra.update(f"clients/{request.daftra_client_id}.json", {"Client": {
            "category_id": data["category"], "category": data.get("category_name") or "",
        }})


def daftra_failed(error: DaftraError) -> SyncError:
    return SyncError(f"تعذر الإنشاء في دفترة: {error}", from_daftra=True)


def sales_person(request: Request) -> int:
    """The submitter's Daftra staff id, the sales person on the invoice."""
    staff_id = request.created_by.daftra_staff_id
    if not staff_id:
        raise SyncError(f"الموظف «{request.created_by.full_name or request.created_by.username}» غير مربوط "
                        "بموظف في دفترة. اربطه من الإدارة ← المستخدمون، ثم اعتمد الطلب مرة أخرى.")
    return staff_id


def payment_inputs(data: dict) -> tuple[Decimal, str | None]:
    """The amount paid now and its Daftra payment method key, checked before anything is sent."""
    paid = money(data.get("paid_amount"))
    method = PAYMENT_METHOD_KEYS.get(data.get("payment_method"))
    if paid > 0 and not method:
        raise SyncError(f"طريقة الدفع «{data.get('payment_method') or '—'}» غير معروفة لدفترة.")
    return paid, method


def finish(request: Request, invoice: dict, paid: Decimal, method: str | None, reviewer: User, db: Session,
           invoice_pdf_after_payment: bool = False) -> dict:
    """The steps every request shares once its invoice exists: the receipt, and both PDFs.
    invoice_pdf_after_payment: the invoice PDF is taken after the payment, so it shows it."""
    pdf_saved = False if invoice_pdf_after_payment else save_invoice_pdf(request, invoice, db)
    if paid > 0 and request.daftra_payment_id is None:
        ensure_payment(request, invoice, paid, method, reviewer)
        if invoice_pdf_after_payment:
            invoice = get_invoice(request.daftra_invoice_id)
    if invoice_pdf_after_payment:
        pdf_saved = save_invoice_pdf(request, invoice, db)
    receipt_saved = paid > 0 and save_receipt_pdf(request, invoice, paid, reviewer, db)
    return {"daftra_invoice_no": request.daftra_invoice_no, "daftra_receipt_no": request.daftra_receipt_no,
            "invoice_pdf_saved": pdf_saved, "receipt_pdf_saved": receipt_saved}


# ---------- Lines ----------

def invoice_items(data: dict, db: Session) -> list[dict]:
    """The InvoiceItem rows for the order lines, checked before anything is sent to Daftra."""
    lines = data.get("order_lines") or []
    ids = [int(line["product_id"]) for line in lines if str(line.get("product_id", "")).isdigit()]
    products = {product.id: product for product in db.scalars(select(Product).where(Product.id.in_(ids)))}
    items, inscriptions, missing = [], [], []
    seen_groups = set()
    for line in lines:
        product = products.get(int(line["product_id"])) if str(line.get("product_id", "")).isdigit() else None
        if product is None or not product.daftra_id:
            missing.append(line.get("name") or str(line.get("product_id")))
            continue
        price = line.get("unit_price")
        count = package_quantity(line)
        item = {
            "product_id": product.daftra_id, "item": product.name,
            "unit_price": float(money(product.unit_price if price is None else price)),
            "quantity": line["quantity"], "tax1": settings.daftra_tax_id, "store_id": settings.daftra_store_id,
        }
        if product.description:
            item["description"] = product.description
        items.append(item)

        # A package's details are copied onto each of its lines, so its inscription is invoiced once
        if line.get("group_id") and line["group_id"] in seen_groups:
            continue
        if line.get("group_id"):
            seen_groups.add(line["group_id"])
        details = line.get("details") or {}
        text = str(details.get("inscription") or "").strip()
        inscription_price = money(details.get("inscription_price"))
        if text and text not in NO_INSCRIPTION and inscription_price > 0:
            inscriptions.append({
                "product_id": settings.daftra_inscription_product_id, "item": "service", "description": text,
                "unit_price": float(inscription_price), "quantity": count,
                "tax1": settings.daftra_tax_id, "store_id": settings.daftra_store_id,
            })
    if missing:
        raise SyncError("هذه المنتجات غير مربوطة بمنتج في دفترة: " + "، ".join(missing)
                        + ". أضف «رقم دفترة» لكل منها من الإدارة ← المنتجات والباقات، ثم اعتمد الطلب مرة أخرى.")
    if not items:
        raise SyncError("لا توجد منتجات في الطلب لإصدار فاتورة بها.")
    return items + inscriptions


# ---------- Client ----------

def client_id(data: dict, db: Session) -> int:
    """The Daftra client this request is for: an existing one, else a new one."""
    found = existing_client_id(data, db)
    return found if found is not None else create_client(data, local_phone(data.get("phone")), db)


def existing_client_id(data: dict, db: Session) -> int | None:
    """The Daftra client with the request's client code, else its phone number; None if there is none."""
    code = digits(data.get("client_code"))
    if code.strip("0"):
        client = db.scalar(select(Client).where(Client.client_code == code.zfill(6)))
        if client is not None:
            return client.daftra_id

    phone = local_phone(data.get("phone"))
    if len(phone) < 9:
        return None
    known = db.scalars(select(Client).where(or_(Client.phone == phone, Client.phone2 == phone))).all()
    if len(known) > 1:
        raise SyncError(f"يوجد أكثر من عميل بالرقم {phone} ولم يُحدَّد كود العميل. "
                        "أعد الطلب للموظف ليكتب كود العميل الصحيح.")
    if known:
        return known[0].daftra_id

    # Our copy of the client list may be older than Daftra's
    rows = daftra.get("clients.json", {"keywords": phone, "limit": 50}).get("data", [])
    found = [row["Client"] for row in rows
             if phone in (local_phone(row["Client"].get("phone1")), local_phone(row["Client"].get("phone2")))]
    if len(found) > 1:
        raise SyncError(f"يوجد في دفترة أكثر من عميل بالرقم {phone}. أعد الطلب للموظف ليكتب كود العميل الصحيح.")
    return int(found[0]["id"]) if found else None


def create_client(data: dict, phone: str, db: Session) -> int:
    name = squash(data.get("customer_name"))
    # اسم الجهاز is not asked on the form any more; a request from before keeps the one typed then
    device = str(data.get("device_name") or "").strip() or settings.daftra_default_device_name
    coordinates = str(data.get("coordinates") or "").strip()
    if not coordinates:
        # Requests submitted before the form asked for them
        raise SyncError("العميل جديد ودفترة تتطلب «الإحداثيات» له، وهي غير موجودة في الطلب. "
                        "أعد الطلب للموظف ليكملها، ثم اعتمده بعد إعادة الإرسال.")
    # Daftra keeps the city in "city" and the area in "state" (see daftra.address_from_daftra, which reads them back)
    body = {
        "Client": {
            "business_name": name, "type": 2, "phone1": phone,
            "address1": data.get("street") or "", "address2": data.get("house") or "",
            "city": data.get("emirate") or "", "state": data.get("area") or "",
            "country_code": "AE", "default_currency_code": "AED",
            **({"category_id": data["category"], "category": data.get("category_name") or ""} if data.get("category") else {}),
        },
        # The account's required client custom fields
        "le_custom_data_client": {
            settings.daftra_client_device_field: device,
            settings.daftra_client_coordinates_field: coordinates,
        },
    }
    new_id = daftra.create("clients.json", body, {"skip_email": 1})
    row = daftra.get(f"clients/{new_id}.json").get("data", {}).get("Client", {})
    db.add(Client(
        daftra_id=new_id, client_code=str(row.get("client_number") or new_id)[:10], customer_name=name, phone=phone,
        addresses=[Address(emirate=data.get("emirate") or "", area=data.get("area") or "", street=data.get("street") or "",
                           house=data.get("house") or "", link=data.get("location_url") or "", is_default=True)],
    ))
    return new_id


# ---------- Invoice ----------

def marker(request: Request) -> str:
    return f"PORTAL-{request.id}"


def get_invoice(invoice_id: int) -> dict:
    return daftra.get(f"invoices/{invoice_id}.json")["data"]["Invoice"]


def find_invoice(request: Request) -> int | None:
    rows = daftra.get("invoices.json", {"client_id": request.daftra_client_id, "limit": 100}).get("data", [])
    return next((int(row["Invoice"]["id"]) for row in rows if row["Invoice"].get("po_number") == marker(request)), None)


def ensure_invoice(request: Request, items: list[dict], staff_id: int, notes: str = "") -> dict:
    data = request.data
    invoice = None
    if request.daftra_invoice_id is not None:
        try:
            invoice = get_invoice(request.daftra_invoice_id)
        except NotFound:
            # Deleted in Daftra since (e.g. because its total was wrong), so it is made again
            request.daftra_invoice_id = request.daftra_invoice_no = None
            request.daftra_payment_id = request.daftra_receipt_no = None
    if invoice is None:
        request.daftra_invoice_id = find_invoice(request)
        if request.daftra_invoice_id is None:
            fields = {
                # Offline like every invoice on the account: not emailed, so the client needs no email
                "client_id": request.daftra_client_id, "date": data.get("request_date"), "draft": 0, "is_offline": 1,
                "currency_code": "AED", "store_id": settings.daftra_store_id, "branch_id": settings.daftra_branch_id,
                "sales_person_id": staff_id, "order_source_id": data.get("order_source"), "po_number": marker(request),
            }
            if notes:
                fields["notes"] = notes
            discount = money(data.get("discount_amount"))
            if discount > 0:
                fields["adjustment_label"] = data.get("discount_label") or "خصم"
                fields["adjustment_value"] = float(-discount)
            request.daftra_invoice_id = daftra.create("invoices.json", {"Invoice": fields, "InvoiceItem": items})
        invoice = get_invoice(request.daftra_invoice_id)
    request.daftra_invoice_no = invoice.get("no")

    expected, actual = money(data.get("total_amount")), money(invoice.get("summary_total"))
    if abs(expected - actual) > TOTAL_TOLERANCE:
        raise SyncError(
            f"أُنشئت الفاتورة {request.daftra_invoice_no} في دفترة لكن إجماليها {actual} لا يساوي إجمالي الطلب "
            f"{expected}. صحّح الفاتورة في دفترة أو احذفها، ثم اعتمد الطلب مرة أخرى.", from_daftra=True,
        )
    return invoice


def save_invoice_pdf(request: Request, invoice: dict, db: Session) -> bool:
    """Attaches the invoice PDF to the request once. A PDF that cannot be fetched does not stop the
    approval: the invoice exists, and can be printed from Daftra."""
    if any(a.field == INVOICE_ATTACHMENT_FIELD for a in request.attachments):
        return True
    url = invoice.get("invoice_pdf_url")
    if not url:
        return False
    try:
        content = daftra.invoice_pdf(request.daftra_invoice_id, url)
    except DaftraError:
        return False
    attach_pdf(request, INVOICE_ATTACHMENT_FIELD, "فاتورة", invoice, content, db)
    return True


def attach_pdf(request: Request, field: str, title: str, invoice: dict, content: bytes, db: Session):
    """Saves a PDF on the request, named like the ones staff save by hand: «<title> <customer> <client number>.pdf»."""
    client_number = (invoice.get("Client") or {}).get("client_number") or ""
    customer = squash(request.data.get("customer_name"))
    filename = " ".join(part for part in (title, customer, client_number) if part) + ".pdf"
    folder = UPLOAD_DIR / str(request.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex + ".pdf"
    (folder / stored_name).write_bytes(content)
    db.add(Attachment(request=request, field=field, filename=filename[:255], stored_name=stored_name,
                      content_type="application/pdf", size=len(content)))


# ---------- Receipt ----------

def payment_of(request: Request, invoice: dict) -> int | None:
    """The payment this request already made on the invoice, found by the marker in its notes."""
    return next((int(p["id"]) for p in invoice.get("InvoicePayment") or []
                 if (p.get("notes") or "").strip() == marker(request)), None)


def ensure_payment(request: Request, invoice: dict, paid: Decimal, method: str, reviewer: User):
    data = request.data
    existing = payment_of(request, invoice)
    if existing:
        request.daftra_payment_id = existing
    else:
        fields = {
            "invoice_id": request.daftra_invoice_id, "amount": float(paid), "payment_method": method,
            "treasury_id": data.get("treasury"), "date": data.get("payment_date"),
            "transaction_id": data.get("payment_reference") or "", "notes": marker(request),
        }
        # Daftra prints this staff member as the receipt's المستلم; without it, "API"
        if reviewer.daftra_staff_id:
            fields["staff_id"] = reviewer.daftra_staff_id
        request.daftra_payment_id = daftra.create("invoice_payments.json", {"InvoicePayment": fields})
    row = daftra.get(f"invoice_payments/{request.daftra_payment_id}.json").get("data", {}).get("InvoicePayment", {})
    request.daftra_receipt_no = row.get("code")


def save_receipt_pdf(request: Request, invoice: dict, paid: Decimal, reviewer: User, db: Session) -> bool:
    """Attaches the receipt PDF once. Like the invoice PDF, failing to make it does not stop the approval."""
    if not request.daftra_receipt_no or any(a.field == RECEIPT_ATTACHMENT_FIELD for a in request.attachments):
        return bool(request.daftra_receipt_no)
    data = request.data
    day = str(data.get("payment_date") or "")
    try:
        content = printouts.receipt(
            number=request.daftra_receipt_no, date=day_month_year(day),
            client=squash(data.get("customer_name")),
            amount=f"{paid:,.2f}".removesuffix(".00"), method=data.get("payment_method") or "",
            invoice_no=request.daftra_invoice_no or "", receiver=display_name(reviewer),
            treasury=data.get("treasury_name") or "",
        )
    except printouts.PrintoutError:
        return False
    attach_pdf(request, RECEIPT_ATTACHMENT_FIELD, "سند قبض", invoice, content, db)
    return True


# ---------- Work order ----------

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
}
# The portal cannot upload a file, and Daftra will not save the other fields while صورة المنتج is empty
PRODUCT_IMAGE_PLACEHOLDER = "لا توجد صورة — أُنشئ من البوابة"
# Colours as staff write them in those fields
COLOR_TEXT = {"أبيض": "اللون الابيض", "أسود": "اللون الاسود", "ذهبي": "اللون الدهبي"}
BASE_TEXT = {"أسود": "لون القاعده ( الاسود)", "أبيض": "لون القاعده ( الابيض )"}


def package_lines(data: dict) -> list[dict]:
    """One line per package (and per standalone product): the one carrying its details."""
    lines = data.get("order_lines") or []
    return [line for i, line in enumerate(lines)
            if not line.get("group_id") or line["group_id"] not in {l.get("group_id") for l in lines[:i]}]


def work_order_custom_fields(request: Request) -> dict:
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
        "product_image": PRODUCT_IMAGE_PLACEHOLDER,
    }
    return {WORK_ORDER_FIELDS[name]: value for name, value in values.items() if value}


def set_work_order_fields(request: Request, row: dict) -> bool:
    """Writes the work order's custom fields, then reads them back: Daftra saves them but answers
    with an error page, so its answer cannot tell whether they were saved. A failure here does not
    stop the approval; the same details are in the work order's description and PDF."""
    fields = work_order_custom_fields(request)
    try:
        daftra.update_unconfirmed(f"work_orders/{request.daftra_work_order_id}.json", {
            # An edit needs these again, as the work order has them
            "WorkOrder": {"title": row.get("title"), "start_date": str(row.get("start_date") or "")[:10],
                          "delivery_date": str(row.get("delivery_date") or "")[:10]},
            "CustomModel": fields,
        })
        # The values show up a moment after Daftra answers
        for attempt in range(4):
            time.sleep(1 + attempt)
            saved = daftra.read_v2("work_order", request.daftra_work_order_id).get("custom_data") or {}
            if all(str(saved.get(key) or "") == str(value) for key, value in fields.items()):
                return True
    except DaftraError:
        pass
    return False


def work_order_title(data: dict, invoice: dict) -> str:
    """Like the ones staff write: what is installed, where, and the client code, e.g.
    «باقة برادة سقيا الخير - 3 صنابير - أسود أبوظبي منطقة العين 4092»."""
    lines = data.get("order_lines") or []
    names = list(dict.fromkeys(line.get("group_name") or line.get("name") or "" for line in lines))
    code = str((invoice.get("Client") or {}).get("client_number") or "").lstrip("0")
    parts = ["، ".join(name for name in names if name), data.get("emirate"), data.get("area"), code]
    return " ".join(str(part).strip() for part in parts if part and str(part).strip())[:250]


def work_order_rows(request: Request, reviewer: User) -> list[str]:
    """What the technicians need, one line each: in the Daftra description and on the PDF.
    Daftra's API cannot set who a work order is for, so the approving manager is written in it."""
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
        text = str(details.get("inscription") or "").strip()
        if text and text not in NO_INSCRIPTION:
            place = f" (مكان الكتابة: {details['inscription_place']})" if details.get("inscription_place") else ""
            rows.append(f"الكتابة: {text}{place}")
        if details.get("manufacturing_notes"):
            rows.append(f"ملاحظات التصنيع: {details['manufacturing_notes']}")
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


def work_order_description(request: Request, reviewer: User) -> str:
    """The rows, ending with the marker that finds the work order again on a retry."""
    return "\n".join([f"■ {row}" for row in work_order_rows(request, reviewer)] + [marker(request)])


def find_work_order(request: Request) -> int | None:
    rows = daftra.get("work_orders.json", {"client_id": request.daftra_client_id, "status": -1, "limit": 100}).get("data", [])
    return next((int(row["WorkOrder"]["id"]) for row in rows
                 if str(row["WorkOrder"].get("client_id")) == str(request.daftra_client_id)
                 and (row["WorkOrder"].get("description") or "").rstrip().endswith(marker(request))), None)


def ensure_work_order(request: Request, invoice: dict, reviewer: User, db: Session):
    """The installation work order for the approving manager: it starts today and is due after the
    request's مدة التركيب. It is linked to the invoice, so the invoice shows it, and its PDF is attached."""
    data = request.data
    if request.daftra_work_order_id is None:
        request.daftra_work_order_id = find_work_order(request)
    if request.daftra_work_order_id is None:
        start = datetime.now(UAE).date()
        days = int(data.get("installation_days") or 20)
        request.daftra_work_order_id = daftra.create("work_orders.json", {"WorkOrder": {
            "title": work_order_title(data, invoice), "client_id": request.daftra_client_id,
            "start_date": start.isoformat(), "delivery_date": (start + timedelta(days=days)).isoformat(),
            "description": work_order_description(request, reviewer),
        }})
    row = daftra.get(f"work_orders/{request.daftra_work_order_id}.json").get("data", {}).get("WorkOrder", {})
    request.daftra_work_order_no = row.get("number")
    if str(invoice.get("work_order_id") or "0") != str(request.daftra_work_order_id):
        daftra.post(f"invoices/assign_work_order/{request.daftra_invoice_id}.json",
                    {"Invoice": {"work_order_id": request.daftra_work_order_id}})
    fields_saved = set_work_order_fields(request, row)
    return save_work_order_pdf(request, row, invoice, reviewer, db), fields_saved


def save_work_order_pdf(request: Request, row: dict, invoice: dict, reviewer: User, db: Session) -> bool:
    """Attaches the work order PDF once; Daftra has no file for a work order, so the portal draws it.
    row: the work order as Daftra returns it, for its number, title and dates."""
    if any(a.field == WORK_ORDER_ATTACHMENT_FIELD for a in request.attachments):
        return True
    start, delivery = str(row.get("start_date") or ""), str(row.get("delivery_date") or "")
    try:
        content = printouts.work_order(
            number=request.daftra_work_order_no or "", title=row.get("title") or work_order_title(request.data, invoice),
            start=day_month_year(start), delivery=day_month_year(delivery),
            days=int(request.data.get("installation_days") or 0), rows=work_order_rows(request, reviewer),
            responsible=display_name(reviewer), sales_person=display_name(request.created_by),
        )
    except printouts.PrintoutError:
        return False
    attach_pdf(request, WORK_ORDER_ATTACHMENT_FIELD, "أمر شغل", invoice, content, db)
    return True


SYNCS = {"new_sale": sync_new_sale, "contract_renewal": sync_contract_renewal, "balance_payment": sync_balance_payment,
         "maintenance": sync_maintenance}
