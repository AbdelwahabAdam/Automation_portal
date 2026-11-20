"""The invoice with its lines, the receipt (سند قبض) for what was paid, and both PDFs."""

import math
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import printouts
from .. import requests
from ...core.errors import SyncError
from ...integrations import daftra
from ..clients import address_fields
from ...core.config import UPLOAD_DIR, settings
from ...integrations.daftra import DaftraError, NotFound
from ..form_engine import NO_INSCRIPTION, package_quantity
from ..catalog import Product
from ...core.text import day_month_year
from .common import (INVOICE_ATTACHMENT_FIELD, RECEIPT_ATTACHMENT_FIELD, TOTAL_TOLERANCE, 
                     attach_pdf, made_before_the_request, marker, money, printed_terms,
                     staff_name)
from .documents import Invoice, Receipt


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


def make_invoice(request, doc: Invoice) -> dict:
    """The request's invoice in Daftra, made once however often the request is approved.

    Sends no «notes»: Daftra shows them in the invoice's الشروط والأحكام box, which holds only
    the terms its packages print (html_notes, see modules/terms), or nothing. The form's ملاحظات
    stay on the request in the portal.

    doc.sales_person: the salesperson who sent the request. Daftra shows them twice, as it does on
    the receipt: «بيعت بواسطة» (sales_person_id) and «أنشئ بواسطة» (staff_id). Without the second one
    Daftra writes the API key's own identity there, which reads «The API»."""
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
                "client_id": request.daftra_client_id, "date": doc.date, "draft": 0, "is_offline": 1,
                "currency_code": "AED", "store_id": settings.daftra_store_id, "branch_id": settings.daftra_branch_id,
                "sales_person_id": doc.sales_person, "staff_id": doc.sales_person, "po_number": marker(request),
                # The address this request is for, printed on the invoice. Without it the invoice
                # carries whatever the client record holds, which may be another of their addresses
                # or nothing at all. Sent only when the form has one, so it can never blank it.
                **doc.address,
                # Left out rather than sent empty when the form does not ask for it, or does not insist
                **({"order_source_id": doc.order_source} if doc.order_source else {}),
            }
            discount = money(doc.discount)
            if discount > 0:
                fields["adjustment_label"] = doc.discount_label or "خصم"
                fields["adjustment_value"] = float(-discount)
            term = doc.terms
            if term is not None:
                fields["html_notes"] = printed_terms.as_html(term.body)
            # The same check as the one below, made before anything is sent: the lines about to go
            # add up to what the request says, or nothing is created. Without it a request whose
            # total cannot be matched still leaves an invoice behind in Daftra on every approval,
            # for someone to find and delete by hand. The invoice's total is its lines less the
            # discount, as its prices already carry the VAT.
            lines_total = sum(money(item.get("unit_price")) * money(item.get("quantity"))
                              for item in doc.items)
            if abs(lines_total - discount - money(doc.total)) > TOTAL_TOLERANCE:
                raise SyncError(
                    f"بنود الطلب تساوي {lines_total - discount:.2f} بينما إجمالي الطلب "
                    f"{money(doc.total):.2f}. صحّح الطلب ثم اعتمده مرة أخرى.")
            request.save_document(
                "invoice", daftra.create("invoices.json", {"Invoice": fields, "InvoiceItem": list(doc.items)}))
            request.printed_terms_id, request.printed_terms = (term.id, term.label) if term else (None, None)
        invoice = get_invoice(request.daftra_invoice_id)
    request.save_document("invoice", request.daftra_invoice_id, invoice.get("no") or "")

    expected, actual = money(doc.total), money(invoice.get("summary_total"))
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


def same_payment(payment: dict, request, receipt: Receipt, amount: Decimal | None = None) -> bool:
    """Whether a payment already on the invoice is the one this receipt would make, going by what
    Daftra keeps of a payment the API made: its amount, its method, its transfer number, that the
    API made it (or the receipt's own staff member, should Daftra ever keep the one it is sent),
    and that it is not older than the request. A payment made by hand in Daftra is never taken for
    the portal's own: who made it is part of what is matched.

    amount: the part of the receipt this payment would be — what pays the invoice by default, or
    what goes to the client's balance (credit_of)."""
    return (str(payment.get("status") or "1") == "1"
            and money(payment.get("amount")) == (receipt.to_invoice if amount is None else amount)
            and (payment.get("payment_method") or "") == (receipt.method_key or "")
            and str(payment.get("transaction_id") or "").strip() == str(receipt.reference or "").strip()
            and str(payment.get("staff_id")) in {str(settings.daftra_api_staff_id), str(receipt.received_by)}
            and not made_before_the_request(request, payment.get("created")))


def payment_of(request, invoice: dict, receipt: Receipt | None = None, db: Session | None = None) -> int | None:
    """The payment this request already made on the invoice, when an earlier try of the approval
    got that far and Daftra's answer never came back, so the request does not hold it.

    By the marker in its notes, where Daftra kept it (its first line: a payment with no invoice of
    its own to carry them, طلب تسديد مبلغ متبقي, holds the salesperson's ملاحظات under it). Our
    account does not keep it: every payment the portal made there has empty notes. With the marker
    alone, a payment whose answer timed out was made a second time on the next try (request 204,
    invoice 06651: receipts 030226 and 030228 for one transfer).

    So, given the receipt, also by what Daftra does keep (same_payment), and held by no other
    request: two requests paying the same amount on one invoice each get a payment of their own.
    """
    payments = invoice.get("InvoicePayment") or []
    marked = next((int(p["id"]) for p in payments
                   if (p.get("notes") or "").strip().splitlines()[:1] == [marker(request)]), None)
    if marked is not None or receipt is None:
        return marked
    for payment in payments:
        if not same_payment(payment, request, receipt):
            continue
        holder = requests.document_holder(db, "payment", int(payment["id"])) if db is not None else None
        if holder in (None, request.id):
            return int(payment["id"])
    return None


def unanswered(error: DaftraError) -> bool:
    """Whether Daftra may have done what it was asked although no answer came: anything but its own
    refusal (HTTP 4xx). A timeout, a dropped connection, a 5xx — it has saved a record after each."""
    return not str(error).startswith("HTTP 4")


def seconds_left_to_wait(request) -> int:
    """How long before a payment Daftra left unanswered may be sent again; 0 when there is nothing
    to wait for. Counted from when the portal stopped waiting for the answer, not from each try
    since: trying again does not start the wait over."""
    sent = request.payment_unanswered_at
    if sent is None:
        return 0
    passed = (datetime.now(timezone.utc) - sent).total_seconds()
    return max(0, math.ceil(settings.daftra_unanswered_payment_wait_seconds - passed))


def wait_in_words(seconds: int) -> str:
    """The wait as the manager is told it: «دقيقتين» for the usual two minutes."""
    if seconds == 120:
        return "دقيقتين"
    if seconds == 60:
        return "دقيقة"
    return f"{seconds} ثانية"


def make_payment(request, invoice: dict, receipt: Receipt, db: Session | None = None):
    """The receipt (سند قبض) against the request's invoice, made once.

    receipt.notes: for a form whose only record in Daftra is this payment, so its ملاحظات has a
    home. The marker stays the first line, which finds the payment again where Daftra keeps it;
    where it does not, payment_of knows the payment by its amount, method and transfer number."""
    existing = payment_of(request, invoice, receipt, db)
    if existing:
        request.save_document("payment", existing)
    else:
        # Sent before and left unanswered: Daftra may be recording it still, and it is not on the
        # invoice yet. Nothing is sent again until it has had its time; once it shows up, the
        # check above takes it at once, however little of the wait has gone.
        left = seconds_left_to_wait(request)
        if left > 0:
            raise SyncError(
                "أُرسل طلب تسجيل الدفعة إلى دفترة ولم يصل ردها، وقد تظهر الدفعة على الفاتورة خلال لحظات. "
                f"انتظر {left} ثانية ثم اعتمد الطلب مرة أخرى؛ لن تُسجَّل الدفعة مرتين.")
        fields = {
            "invoice_id": request.daftra_invoice_id, "amount": float(receipt.to_invoice),
            "payment_method": receipt.method_key, "treasury_id": receipt.treasury, "date": receipt.date,
            "transaction_id": receipt.reference or "",
            "notes": "\n".join([marker(request), *([receipt.notes] if receipt.notes else [])]),
            # Daftra prints this staff member as the receipt's المستلم: the salesperson who sent the
            # request, not the manager approving it. Without one it prints "API", so one is required.
            "staff_id": receipt.received_by,
        }
        try:
            made = daftra.create("invoice_payments.json", {"InvoicePayment": fields})
        except DaftraError as error:
            if not unanswered(error):
                raise
            # Not «تعذر الإنشاء»: Daftra has recorded a payment a minute after the portal stopped
            # waiting for its answer. Approving again at once would not see it yet and pay twice,
            # so the time is kept (the failed approval saves it with the request) and the next
            # try waits for it above.
            request.payment_unanswered_at = datetime.now(timezone.utc)
            raise SyncError(
                "لم يصل رد دفترة على تسجيل الدفعة، وقد تكون سُجّلت فيها. "
                f"انتظر {wait_in_words(settings.daftra_unanswered_payment_wait_seconds)} ثم اعتمد الطلب مرة "
                "أخرى: إن كانت الدفعة قد سُجّلت فستتعرف عليها البوابة ولن تكررها. "
                f"({error})", from_daftra=True) from error
        request.save_document("payment", made)
    # Known now, one way or the other: nothing is left to wait for
    request.payment_unanswered_at = None
    row = daftra.get(f"invoice_payments/{request.daftra_payment_id}.json").get("data", {}).get("InvoicePayment", {})
    request.save_document("payment", request.daftra_payment_id, row.get("code") or "")


# The document a request keeps for what it put on the client's balance (RequestDocument.kind)
CLIENT_CREDIT = "client_credit"


def credit_of(request, receipt: Receipt, db: Session | None = None) -> int | None:
    """The payment to the client's balance this request already made, when an earlier try of the
    approval got that far and Daftra's answer never came back. Known as an invoice's payment is
    (same_payment), among the payments Daftra holds for the client on no invoice, and held by no
    other request."""
    for payment in daftra.client_payments(request.daftra_client_id):
        if not same_payment(payment, request, receipt, receipt.credit):
            continue
        holder = requests.document_holder(db, CLIENT_CREDIT, int(payment["id"])) if db is not None else None
        if holder in (None, request.id):
            return int(payment["id"])
    return None


def make_client_credit(request, receipt: Receipt, db: Session | None = None):
    """What the client paid beyond the invoice, recorded as their own balance in Daftra (رصيد العميل,
    which the client's page shows as الدائن): a payment of theirs on no invoice, made once.

    Put on the invoice instead, it would stand there as a negative remainder until someone settled
    it by hand in Daftra — whose own «تحويل المبلغ الزائد إلى رصيد العميل» makes exactly this.

    status 1 and the currency go with it because Daftra keeps neither unless sent (tried on the
    live account, 2026-11-20): without a status the payment is saved but not listed among the
    client's payments, and without a currency it is not counted in الدائن on the client's page.
    Made, found again and waited for exactly as the invoice's payment is (make_payment)."""
    existing = credit_of(request, receipt, db)
    if existing:
        request.save_document(CLIENT_CREDIT, existing)
    else:
        left = seconds_left_to_wait(request)
        if left > 0:
            raise SyncError(
                "أُرسل طلب تسجيل الزيادة في رصيد العميل إلى دفترة ولم يصل ردها، وقد تظهر خلال لحظات. "
                f"انتظر {left} ثانية ثم اعتمد الطلب مرة أخرى؛ لن تُسجَّل مرتين.")
        fields = {
            "client_id": request.daftra_client_id, "amount": float(receipt.credit),
            "payment_method": receipt.method_key, "treasury_id": receipt.treasury, "date": receipt.date,
            "transaction_id": receipt.reference or "", "status": 1, "currency_code": "AED",
            "notes": marker(request), "staff_id": receipt.received_by,
        }
        try:
            made = daftra.create("client_payments.json", {"ClientPayment": fields})
        except DaftraError as error:
            if not unanswered(error):
                raise
            request.payment_unanswered_at = datetime.now(timezone.utc)
            raise SyncError(
                "لم يصل رد دفترة على تسجيل الزيادة في رصيد العميل، وقد تكون سُجّلت فيها. "
                f"انتظر {wait_in_words(settings.daftra_unanswered_payment_wait_seconds)} ثم اعتمد الطلب مرة "
                "أخرى: إن كانت قد سُجّلت فستتعرف عليها البوابة ولن تكررها. "
                f"({error})", from_daftra=True) from error
        request.save_document(CLIENT_CREDIT, made)
    request.payment_unanswered_at = None
    row = daftra.get(f"client_payments/{request.daftra_credit_id}.json").get("data", {}).get("ClientPayment", {})
    request.save_document(CLIENT_CREDIT, request.daftra_credit_id, row.get("code") or "")


def save_receipt_pdf(request, invoice: dict, receipt: Receipt, db: Session) -> bool:
    """Attaches the receipt PDF once. Like the invoice PDF, failing to make it does not stop the approval."""
    if not request.daftra_receipt_no or any(a.field == RECEIPT_ATTACHMENT_FIELD for a in request.attachments):
        return bool(request.daftra_receipt_no)
    day = str(receipt.date or "")
    try:
        content = printouts.receipt(
            number=request.daftra_receipt_no, date=day_month_year(day), client=receipt.client_name,
            amount=f"{receipt.to_invoice:,.2f}".removesuffix(".00"), method=receipt.method or "",
            invoice_no=request.daftra_invoice_no or "",
            receiver=staff_name(receipt.received_by, request.created_by),
            treasury=receipt.treasury_name or "",
        )
    except printouts.PrintoutError:
        return False
    attach_pdf(request, RECEIPT_ATTACHMENT_FIELD, "سند قبض", invoice, content, db)
    return True


def finish_invoice(request, invoice: dict, receipt: Receipt | None, db: Session) -> dict:
    """The steps every request shares once its invoice exists: the payment, the receipt, both PDFs.

    receipt None: nothing was paid now, so no payment is made and no receipt drawn.
    What the receipt holds beyond the invoice (receipt.credit) goes to the client's balance, after
    the invoice's own payment: a receipt of its own in Daftra, kept on the request with its number."""
    paid = receipt.to_invoice if receipt is not None else Decimal(0)
    credit = receipt.credit if receipt is not None else Decimal(0)
    if paid > 0 and request.daftra_payment_id is None:
        make_payment(request, invoice, receipt, db)
        invoice = get_invoice(request.daftra_invoice_id)
    if credit > 0 and request.daftra_credit_id is None:
        make_client_credit(request, receipt, db)
    # Daftra draws the PDF from the invoice as it stands, so it is taken after the payment: taken
    # before, «مدفوع» reads 0 and «الرصيد المستحق» the whole total, whatever the client just paid
    pdf_saved = save_invoice_pdf(request, invoice, db)
    receipt_saved = paid > 0 and save_receipt_pdf(request, invoice, receipt, db)
    summary = {"daftra_invoice_no": request.daftra_invoice_no, "daftra_receipt_no": request.daftra_receipt_no,
               "invoice_pdf_saved": pdf_saved, "receipt_pdf_saved": receipt_saved,
               "payment_proof_sent": send_payment_proof(request, invoice)}
    if credit > 0:
        summary.update(daftra_credit_no=request.daftra_credit_no, client_credit=float(credit))
    return summary
