"""The invoice with its lines, the receipt (سند قبض) for what was paid, and both PDFs."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import printouts
from ...core.errors import SyncError
from ...integrations import daftra
from ..clients import address_fields
from ...core.config import UPLOAD_DIR, settings
from ...integrations.daftra import DaftraError, NotFound
from ..form_engine import NO_INSCRIPTION, package_quantity
from ..catalog import Product
from ...core.text import day_month_year, squash
from .common import (INVOICE_ATTACHMENT_FIELD, RECEIPT_ATTACHMENT_FIELD, TOTAL_TOLERANCE, 
                     attach_pdf, made_before_the_request, marker, money, printed_terms, sales_person,
                     sales_person_name, terms_to_print)


def invoice_address(data: dict) -> dict:
    """The request's address as an invoice carries it, or nothing when the form has no address:
    sending it empty would clear what Daftra would otherwise print from the client."""
    address = address_fields(data)
    if not any(address[key] for key in ("address1", "address2", "city", "state")):
        return {}
    return {f"client_{name}": value for name, value in address.items()}


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
        # What the salesperson wrote about this line stands in for it (اعمال اضافية: «أخرى» is the
        # catalog's own «service» product, so only the description says what the work was)
        described = str((line.get("details") or {}).get("work_description") or "").strip()
        if described:
            item["description"] = described
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


def find_invoice(request) -> int | None:
    """The invoice this request already made, if the last approval got that far. An older invoice
    wearing the same mark belongs to someone else's request, and is not taken for this one's."""
    rows = daftra.get("invoices.json", {"client_id": request.daftra_client_id, "limit": 100}).get("data", [])
    return next((int(row["Invoice"]["id"]) for row in rows
                 if row["Invoice"].get("po_number") == marker(request)
                 and not made_before_the_request(request, row["Invoice"].get("created"))), None)


def ensure_invoice(request, items: list[dict], staff_id: int) -> dict:
    """Sends no «notes»: Daftra shows them in the invoice's الشروط والأحكام box, which holds only
    the terms its packages print (html_notes, see modules/terms), or nothing. The form's ملاحظات
    stay on the request in the portal.

    staff_id: the salesperson who sent the request. Daftra shows them twice, as it does on the
    receipt: «بيعت بواسطة» (sales_person_id) and «أنشئ بواسطة» (staff_id). Without the second one
    Daftra writes the API key's own identity there, which reads «The API»."""
    data = request.data
    invoice = None
    if request.daftra_invoice_id is not None:
        try:
            invoice = get_invoice(request.daftra_invoice_id)
            # An invoice another portal made can be written here by a failed approval, from back
            # when one mark could belong to two portals. It is not ours to invoice against or to
            # pay — it carries their mark, or it is older than this request — so let it go and
            # make our own. Both are needed: a portal that shared our prefix wrote our very mark.
            if ((invoice.get("po_number") or "") != marker(request)
                    or made_before_the_request(request, invoice.get("created"))):
                invoice = None
                raise NotFound("not this request's invoice")
        except NotFound:
            # Deleted in Daftra since (e.g. because its total was wrong), so it is made again
            request.forget_document("invoice")
            request.forget_document("payment")
    if invoice is None:
        request.save_document("invoice", find_invoice(request))
        if request.daftra_invoice_id is None:
            fields = {
                # Offline like every invoice on the account: not emailed, so the client needs no email
                "client_id": request.daftra_client_id, "date": data.get("request_date"), "draft": 0, "is_offline": 1,
                "currency_code": "AED", "store_id": settings.daftra_store_id, "branch_id": settings.daftra_branch_id,
                "sales_person_id": staff_id, "staff_id": staff_id, "po_number": marker(request),
                # The address this request is for, printed on the invoice. Without it the invoice
                # carries whatever the client record holds, which may be another of their addresses
                # or nothing at all. Sent only when the form has one, so it can never blank it.
                **invoice_address(data),
                # Left out rather than sent empty when the form does not ask for it, or does not insist
                **({"order_source_id": data["order_source"]} if data.get("order_source") else {}),
            }
            discount = money(data.get("discount_amount"))
            if discount > 0:
                fields["adjustment_label"] = data.get("discount_label") or "خصم"
                fields["adjustment_value"] = float(-discount)
            term = terms_to_print(request)
            if term is not None:
                fields["html_notes"] = printed_terms.as_html(term.body)
            request.save_document(
                "invoice", daftra.create("invoices.json", {"Invoice": fields, "InvoiceItem": items}))
            request.printed_terms_id, request.printed_terms = (term.id, term.label) if term else (None, None)
        invoice = get_invoice(request.daftra_invoice_id)
    request.save_document("invoice", request.daftra_invoice_id, invoice.get("no") or "")

    expected, actual = money(data.get("total_amount")), money(invoice.get("summary_total"))
    if abs(expected - actual) > TOTAL_TOLERANCE:
        raise SyncError(
            f"أُنشئت الفاتورة {request.daftra_invoice_no} في دفترة لكن إجماليها {actual} لا يساوي إجمالي الطلب "
            f"{expected}. صحّح الفاتورة في دفترة أو احذفها، ثم اعتمد الطلب مرة أخرى.", from_daftra=True,
        )
    return invoice


def save_invoice_pdf(request, invoice: dict, db: Session) -> bool:
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


# The form field the sales person uploads إثبات الدفع under, which goes on the Daftra invoice
PAYMENT_PROOF_FIELD = "payment_proof"


def send_payment_proof(request, invoice: dict) -> bool:
    """Shows the إثبات الدفع the sales person uploaded on the invoice in Daftra, once.

    Two steps: the file goes into Daftra's file store, then its id is linked to the invoice.
    Best effort, like the PDFs — the invoice and its receipt already exist, so a proof that
    cannot be sent does not stop the approval, and the approval's log says it was not sent.

    Off unless settings.daftra_send_payment_proof says otherwise.
    """
    if not settings.daftra_send_payment_proof:
        return False
    if invoice.get("InvoiceDocument"):
        return True
    sent = False
    for attachment in request.attachments:
        if attachment.field != PAYMENT_PROOF_FIELD:
            continue
        try:
            content = (UPLOAD_DIR / str(attachment.request_id) / attachment.stored_name).read_bytes()
        except OSError:
            continue
        try:
            file_id = daftra.upload_file(content, attachment.filename, attachment.content_type)
            daftra.attach_invoice_document(request.daftra_invoice_id, file_id)
        except DaftraError:
            continue
        sent = True
    return sent


def payment_of(request, invoice: dict) -> int | None:
    """The payment this request already made on the invoice, found by the marker in its notes.

    The marker is the first line: a payment with no invoice of its own to carry them (طلب تسديد
    مبلغ متبقي) holds the salesperson's ملاحظات on the lines under it.
    """
    return next((int(p["id"]) for p in invoice.get("InvoicePayment") or []
                 if (p.get("notes") or "").strip().splitlines()[:1] == [marker(request)]), None)


def ensure_payment(request, invoice: dict, paid: Decimal, method: str, notes: str = ""):
    """notes: for a form whose only record in Daftra is this payment, so its ملاحظات has a home.
    The marker stays the first line, which is what finds the payment again."""
    data = request.data
    existing = payment_of(request, invoice)
    if existing:
        request.save_document("payment", existing)
    else:
        fields = {
            "invoice_id": request.daftra_invoice_id, "amount": float(paid), "payment_method": method,
            "treasury_id": data.get("treasury"), "date": data.get("payment_date"),
            "transaction_id": data.get("payment_reference") or "",
            "notes": "\n".join([marker(request), *([notes] if notes else [])]),
            # Daftra prints this staff member as the receipt's المستلم: the salesperson who sent the
            # request, not the manager approving it. Without one it prints "API", so one is required.
            "staff_id": sales_person(request),
        }
        request.save_document("payment",
                              daftra.create("invoice_payments.json", {"InvoicePayment": fields}))
    row = daftra.get(f"invoice_payments/{request.daftra_payment_id}.json").get("data", {}).get("InvoicePayment", {})
    request.save_document("payment", request.daftra_payment_id, row.get("code") or "")


def save_receipt_pdf(request, invoice: dict, paid: Decimal, db: Session) -> bool:
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
            invoice_no=request.daftra_invoice_no or "", receiver=sales_person_name(request),
            treasury=data.get("treasury_name") or "",
        )
    except printouts.PrintoutError:
        return False
    attach_pdf(request, RECEIPT_ATTACHMENT_FIELD, "سند قبض", invoice, content, db)
    return True


def finish(request, invoice: dict, paid: Decimal, method: str | None, db: Session,
           payment_notes: str = "") -> dict:
    """The steps every request shares once its invoice exists: the payment, the receipt, both PDFs.

    payment_notes: passed on to the payment, for a form that makes no invoice of its own."""
    if paid > 0 and request.daftra_payment_id is None:
        ensure_payment(request, invoice, paid, method, notes=payment_notes)
        invoice = get_invoice(request.daftra_invoice_id)
    # Daftra draws the PDF from the invoice as it stands, so it is taken after the payment: taken
    # before, «مدفوع» reads 0 and «الرصيد المستحق» the whole total, whatever the client just paid
    pdf_saved = save_invoice_pdf(request, invoice, db)
    receipt_saved = paid > 0 and save_receipt_pdf(request, invoice, paid, db)
    return {"daftra_invoice_no": request.daftra_invoice_no, "daftra_receipt_no": request.daftra_receipt_no,
            "invoice_pdf_saved": pdf_saved, "receipt_pdf_saved": receipt_saved,
            "payment_proof_sent": send_payment_proof(request, invoice)}
