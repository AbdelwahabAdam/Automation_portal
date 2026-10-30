"""What approving a request creates in Daftra, and the printouts the portal draws itself.

Today's `daftra_sync`, renamed: the new name also ends the mix-up with `daftra_refresh` that the
README used to warn about.

This module holds the steps, not the order they run in. What each form creates, and in what
order, is in that form's own folder (`app/forms/<key>/hooks.py`); `requests` asks the form when a
manager approves. Each step keeps the id it got on the request before the next one starts, so
approving again after a failure carries on from the step that failed. If an id was lost (the
answer never arrived), the invoice is found again by its po_number and the payment by its notes,
both "<prefix>-<request id>", so neither is created twice.
"""

from .common import (INVOICE_ATTACHMENT_FIELD, RECEIPT_ATTACHMENT_FIELD, TOTAL_TOLERANCE,
                     WORK_ORDER_ATTACHMENT_FIELD, attach_pdf, daftra_failed, made_before_the_request,
                     marker, money, payment_inputs, reports_daftra_errors, sales_person)
from .estimate import ESTIMATE_ATTACHMENT_FIELD, ensure_estimate, find_estimate, get_estimate, save_estimate_pdf
from .invoice import (ensure_invoice, ensure_payment, finish, get_invoice, invoice_items, payment_of,
                      save_invoice_pdf, save_receipt_pdf)
from .payment_methods import PAYMENT_METHOD_KEYS
from .work_order import ensure_work_order, find_work_order, work_order_values

__all__ = [
    "ESTIMATE_ATTACHMENT_FIELD", "INVOICE_ATTACHMENT_FIELD", "PAYMENT_METHOD_KEYS",
    "RECEIPT_ATTACHMENT_FIELD", "TOTAL_TOLERANCE", "WORK_ORDER_ATTACHMENT_FIELD", "attach_pdf",
    "daftra_failed", "ensure_estimate", "ensure_invoice", "ensure_payment", "ensure_work_order",
    "find_estimate", "find_work_order", "finish", "get_estimate", "get_invoice", "invoice_items",
    "made_before_the_request", "marker", "money", "payment_inputs", "payment_of",
    "reports_daftra_errors", "sales_person", "save_estimate_pdf", "save_invoice_pdf",
    "save_receipt_pdf", "work_order_values",
]
