"""Making a form's documents in Daftra, in the order its output.py lists them.

    DOCUMENTS = [client, invoice, receipt, work_order]
    on_approve = approve(DOCUMENTS)

Every function is called first, and only then is anything sent: a check one of them makes — a
product not linked to Daftra, a payment method Daftra does not know — stops the approval before
the client or anything else is made. Each document's id is kept on the request as it is made, so
approving again after a failure carries on from the one that failed.

The order is the form's, with three rules the documents themselves impose:
- a Receipt pays the Invoice (or ExistingInvoice) just before it;
- a WorkOrder is linked to the Invoice made before it;
- the invoice's PDF is taken after its receipt, because Daftra draws it as it stands — taken
  before, «مدفوع» reads 0 whatever the client just paid.
"""

from typing import Callable

from ...core.errors import SyncError
from ...integrations.daftra import NotFound
from .. import notifications, requests
from ..clients import client_id, existing_client_id, update_client
from .client_email import send_invoice_email
from .common import TOTAL_TOLERANCE, money, reports_daftra_errors, terms_to_print
from .documents import ClientRecord, Estimate, ExistingInvoice, Invoice, InvoiceEmail, Receipt, WorkOrder
from .estimate import make_estimate, save_estimate_pdf
from .invoice import finish_invoice, get_invoice, invoice_address, invoice_items, make_invoice, payment_of
from .work_order import make_work_order


def approve(documents: list[Callable]) -> Callable:
    """The form's on_approve: its documents, made in this order."""
    @reports_daftra_errors
    def on_approve(ctx) -> dict:
        return run(ctx, documents)
    on_approve.documents = tuple(documents)
    return on_approve


def run(ctx, documents: list[Callable]) -> dict:
    """Makes the documents, and returns what the activity log records of them."""
    request, db, reviewer = ctx.request, ctx.db, ctx.reviewer
    # Every one built before any is sent, so every check comes first
    built = [doc for doc in (make(ctx) for make in documents) if doc is not None]
    summary: dict = {}
    invoice: dict | None = None
    # An invoice whose receipt and PDFs are still to do
    open_invoice = False
    # An invoice Daftra already had, which the receipt after it must not overpay
    existing: ExistingInvoice | None = None

    def close(receipt: Receipt | None):
        nonlocal open_invoice, existing
        if existing is not None and existing.refuse_overpaying and receipt is not None:
            refuse_overpaying(request, invoice, receipt)
        summary.update(finish_invoice(request, invoice, receipt, db))
        open_invoice, existing = False, None

    for doc in built:
        if open_invoice and not isinstance(doc, Receipt):
            close(None)
        if isinstance(doc, ClientRecord):
            make_client(request, doc, db)
        elif isinstance(doc, Estimate):            # before Invoice: an estimate is one too
            estimate = make_estimate(request, doc)
            summary.update(daftra_estimate_no=request.daftra_estimate_no,
                           estimate_pdf_saved=save_estimate_pdf(request, estimate, db))
        elif isinstance(doc, Invoice):
            invoice = make_invoice(request, doc)
            open_invoice = True
        elif isinstance(doc, ExistingInvoice):
            invoice = take_invoice(request, doc)
            open_invoice, existing = True, doc
        elif isinstance(doc, Receipt):
            if not open_invoice:
                raise TypeError("a Receipt pays the Invoice or ExistingInvoice just before it in DOCUMENTS")
            close(doc)
        elif isinstance(doc, WorkOrder):
            if invoice is None:
                raise TypeError("a WorkOrder is linked to an Invoice made before it in DOCUMENTS")
            pdf_saved, fields_saved, staff_assigned = make_work_order(request, invoice, reviewer, db, doc)
            summary.update(work_order_pdf_saved=pdf_saved, work_order_fields_saved=fields_saved,
                           work_order_staff_assigned=staff_assigned,
                           daftra_work_order_no=request.daftra_work_order_no)
        elif isinstance(doc, InvoiceEmail):
            if invoice is None:
                raise TypeError("an InvoiceEmail sends an Invoice made before it in DOCUMENTS")
            summary.update(email_invoice(request, doc, reviewer, db))
        else:
            raise TypeError(f"{type(doc).__name__} is not a document approving can make")
    if open_invoice:
        close(None)
    return summary


def make_client(request, record: ClientRecord, db):
    """The request's Daftra client: found by code or phone, else made — or, when the form does
    not make clients, the error it gives. Then what the form says of a known client is put on it."""
    data = record.as_data()
    if request.daftra_client_id is None:
        if record.if_unknown == "create":
            request.save_document("client", client_id(data, db))
        else:
            found = existing_client_id(data, db)
            if found is None:
                raise SyncError(record.if_unknown)
            request.save_document("client", found)
    if record.keep_in_step:
        update_client(request.daftra_client_id, data, db)


def take_invoice(request, doc: ExistingInvoice) -> dict:
    """The invoice the form chose, kept on the request with its client, as one it had made."""
    request.save_document("invoice", int(doc.invoice_id))
    try:
        invoice = get_invoice(request.daftra_invoice_id)
    except NotFound:
        raise SyncError(f"الفاتورة {doc.name or doc.invoice_id} لم تعد موجودة في دفترة. "
                        "أعد الطلب للموظف ليختار الفاتورة الصحيحة.")
    request.save_document("client", int(invoice["client_id"]))
    request.save_document("invoice", int(doc.invoice_id), invoice.get("no") or "")
    return invoice


def refuse_overpaying(request, invoice: dict, receipt: Receipt):
    """Not more than the invoice still owes — unless this request has already paid it, when what
    is left is what its own payment left."""
    unpaid = money(invoice.get("summary_unpaid"))
    if request.daftra_payment_id is None and not payment_of(request, invoice) and receipt.paid > unpaid + TOTAL_TOLERANCE:
        raise SyncError(f"المبلغ المدفوع {receipt.paid} أكبر من المتبقي على الفاتورة {request.daftra_invoice_no} "
                        f"({unpaid}). أعد الطلب للموظف ليصحح المبلغ.")


def email_invoice(request, doc: InvoiceEmail, reviewer, db) -> dict:
    """The invoice emailed to the client. The approval stands even if it does not go: it is
    recorded, and can be sent again from the request."""
    try:
        to = send_invoice_email(request, doc)
    except notifications.MailError as error:
        return {"invoice_email_failed": str(error)}
    requests.record_event(db, request, reviewer, "invoice_emailed", to)
    return {"invoice_emailed_to": to}


# ---------- what a form's output.py builds its documents from ----------

def order_lines(ctx) -> list[dict]:
    """The invoice lines for the request's المنتجات والباقات, with each package's inscription as a
    line of its own. Refuses — before anything is sent — a product not linked to Daftra."""
    return invoice_items(ctx.data, ctx.db)


def service_address(data: dict) -> dict:
    """The request's address as a document prints it, or {} to print the client's own."""
    return invoice_address(data)


def package_terms(ctx):
    """The terms the first of the request's packages that has one prints on the last page."""
    return terms_to_print(ctx.request)
