"""The invoice with its lines, the receipt (سند قبض) for what was paid, and both PDFs."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import daftra, printouts
from ..config import settings
from ..daftra import DaftraError, NotFound
from ..forms import NO_INSCRIPTION, package_quantity
from ..models import Product, Request, User
from ..text import day_month_year, display_name, squash
from .common import (INVOICE_ATTACHMENT_FIELD, RECEIPT_ATTACHMENT_FIELD, TOTAL_TOLERANCE, SyncError, attach_pdf,
                     marker, money)


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
