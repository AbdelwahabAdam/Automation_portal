"""What approving a request creates in Daftra, and the printouts the portal draws itself.

Today's `daftra_sync`, renamed: the new name also ends the mix-up with `daftra_refresh` that the
README used to warn about.

This module holds the steps, not what goes into them. What each form creates, what goes in
each document and in what order, is in that form's own `app/forms/<key>/output.py` — a list of
functions returning the documents of `documents.py`, which `runner.approve` makes in that order.
`requests` asks the form when a manager approves. Each step keeps the id it got on the request
before the next one starts, so
approving again after a failure carries on from the step that failed. If an id was lost (the
answer never arrived), the invoice is found again by its po_number and the payment by its notes,
both "<prefix>-<request id>", so neither is created twice.
"""

from .common import (INVOICE_ATTACHMENT_FIELD, RECEIPT_ATTACHMENT_FIELD, TOTAL_TOLERANCE,
                     WORK_ORDER_ATTACHMENT_FIELD, attach_pdf, daftra_failed, form_notes,
                     made_before_the_request, marker, money, reports_daftra_errors, sales_person)
from .client_email import send_invoice_email
from .documents import ClientRecord, Estimate, ExistingInvoice, Invoice, InvoiceEmail, Receipt, WorkOrder
from .estimate import (ESTIMATE_ATTACHMENT_FIELD, draw_estimate, find_estimate, get_estimate, make_estimate,
                       save_estimate_pdf)
from .invoice import (finish_invoice, get_invoice, invoice_items, make_invoice, make_payment, payment_of,
                      save_invoice_pdf, save_receipt_pdf)
from .payment_methods import PAYMENT_METHOD_KEYS
from .runner import approve, make_client, order_lines, package_terms, run, service_address
from .work_order import (WORK_ORDER_FIELDS, find_work_order, installation_work_order, make_work_order,
                         work_order_values)

__all__ = [
    # what a form's output.py is written with: the documents, the runner, and what they are built from
    "ClientRecord", "Estimate", "ExistingInvoice", "Invoice", "InvoiceEmail", "Receipt", "WorkOrder",
    "WORK_ORDER_FIELDS", "send_invoice_email",
    "approve", "run", "make_client", "order_lines", "package_terms", "service_address", "installation_work_order",
    "make_estimate", "make_invoice", "make_payment", "make_work_order", "finish_invoice",
    "ESTIMATE_ATTACHMENT_FIELD", "INVOICE_ATTACHMENT_FIELD", "PAYMENT_METHOD_KEYS",
    "RECEIPT_ATTACHMENT_FIELD", "TOTAL_TOLERANCE", "WORK_ORDER_ATTACHMENT_FIELD", "attach_pdf",
    "daftra_failed", "find_estimate", "find_work_order", "form_notes", "get_estimate", "get_invoice",
    "invoice_items", "made_before_the_request", "marker", "money", "payment_of",
    "draw_estimate", "reports_daftra_errors", "sales_person", "save_estimate_pdf", "save_invoice_pdf",
    "save_receipt_pdf", "work_order_values",
]
