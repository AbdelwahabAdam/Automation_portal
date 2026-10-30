"""What every Daftra step shares: amounts, the marker that finds a document again, and saving a
PDF on the request.

The error a manager sees is `core.errors.SyncError`: `clients` raises it too, and neither module
may import the other. The address as Daftra keeps one belongs to `clients`.
"""

import functools
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.errors import SyncError
from ...integrations.daftra import DaftraError
from .. import requests
from .payment_methods import PAYMENT_METHOD_KEYS

from ...core.text import UAE, squash

# The fields the PDFs approving a request saves are attached under (not fields of any form)
INVOICE_ATTACHMENT_FIELD = "daftra_invoice"
RECEIPT_ATTACHMENT_FIELD = "daftra_receipt"
WORK_ORDER_ATTACHMENT_FIELD = "daftra_work_order"
CENT = Decimal("0.01")
# Daftra rounds each line's tax on its own, so a total can be off by a little
TOTAL_TOLERANCE = Decimal("0.05")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def daftra_failed(error: DaftraError) -> SyncError:
    return SyncError(f"تعذر الإنشاء في دفترة: {error}", from_daftra=True)


def reports_daftra_errors(step):
    """Turns Daftra refusing or failing anywhere in a step into the SyncError the manager sees."""
    @functools.wraps(step)
    def run(*args, **kwargs):
        try:
            return step(*args, **kwargs)
        except DaftraError as error:
            raise daftra_failed(error) from error
    return run


def marker(request) -> str:
    """What finds this request's invoice, payment and work order in Daftra again on a retry.

    The prefix says which portal wrote it. Another portal on the same Daftra account — a test one
    on someone's machine — numbers its own requests from 1 as well, and its «PORTAL-12» is not this
    one's: without the prefix, approving request 12 here finds the other's invoice, sees a total
    that does not match, and refuses. Give each portal its own (DAFTRA_MARKER_PREFIX).
    """
    return f"{settings.daftra_marker_prefix}-{request.id}"


def made_before_the_request(request, created: str | None) -> bool:
    """Whether Daftra made this before the request existed, which means it is not the request's own.

    A request's invoice and work order are made when it is approved, so they are always younger
    than it. Anything older carries its mark by accident — another portal's request numbered the
    same, or a request this one was copied from. Daftra stamps its records in the account's own
    time, which is the UAE's. A few minutes are allowed for the two clocks disagreeing.
    """
    try:
        made = datetime.strptime(str(created or "")[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UAE)
    except ValueError:
        return False  # No date to go by: leave it be rather than make a second one
    return made < request.created_at.astimezone(UAE) - timedelta(minutes=5)


def sales_person(request) -> int:
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


def attach_pdf(request, field: str, title: str, invoice: dict, content: bytes, db: Session):
    """Saves a PDF on the request, named like the ones staff save by hand: «<title> <customer> <client number>.pdf».

    The name is ours; the saving is `requests`', which owns the attachments table.
    """
    client_number = (invoice.get("Client") or {}).get("client_number") or ""
    customer = squash(request.data.get("customer_name"))
    filename = " ".join(part for part in (title, customer, client_number) if part) + ".pdf"
    requests.save_file(db, request, field, filename, content)
