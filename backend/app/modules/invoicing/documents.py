"""What a form sends to Daftra, one object per document, each built by the form's `output.py`.

A form's output is a list of functions, each returning one of these (or None: not for this
request), and approving the request makes them in that order:

    def receipt(ctx):
        d = ctx.data
        if not money(d.get("paid_amount")):
            return None
        return Receipt(amount=d["paid_amount"], method=d["payment_method"], ...)

    DOCUMENTS = [client, invoice, receipt, work_order]

The form decides what goes in each field. What no form should repeat stays in the engine, which
these objects never mention: making a document once however often the request is approved,
finding a lost one again by its marker, `is_offline`, the store, the branch, the tax, the total
check, and the PDFs. A few values exist only once an earlier document is made — the client's
number in a work order's title, an invoice's number on the PDF — and the engine fills those in.

Every document is built before any is sent, so a check that fails — a product not linked to
Daftra, a payment method Daftra does not know — stops the approval before anything is made.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ...core.errors import SyncError
from .common import money
from .payment_methods import PAYMENT_METHOD_KEYS


@dataclass(frozen=True)
class ClientRecord:
    """العميل: the Daftra client the request is for, found by its code or phone.

    if_unknown: what happens when neither finds one — "create" makes it (from these fields), and
    any other text is the error the manager is shown instead.
    keep_in_step: what the form says about a known client (its name, type, address…) is put on it.
    """

    phone: str = ""
    phone2: str = ""
    client_code: str = ""
    name: str = ""
    customer_type: str = ""
    gender: str = ""
    email: str = ""
    emirate: str = ""
    area: str = ""
    street: str = ""
    house: str = ""
    category: Any = None
    category_name: str = ""
    location_url: str = ""
    coordinates: str = ""
    device_name: str = ""
    if_unknown: str = "create"
    keep_in_step: bool = True

    def as_data(self) -> dict:
        """The client's fields under the names `modules/clients` reads them by."""
        return {
            "phone": self.phone, "phone2": self.phone2, "client_code": self.client_code,
            "customer_name": self.name, "customer_type": self.customer_type, "gender": self.gender,
            "email": self.email, "emirate": self.emirate, "area": self.area, "street": self.street,
            "house": self.house, "category": self.category, "category_name": self.category_name,
            "location_url": self.location_url, "coordinates": self.coordinates, "device_name": self.device_name,
        }


@dataclass(frozen=True)
class Invoice:
    """الفاتورة.

    total: what Daftra's total must come to, checked once it is made.
    address: the client_* fields printed on it (invoice_address), or {} to print the client's own.
    terms: the term printed on its last page (modules/terms), or None.
    """

    date: str
    items: list[dict]
    sales_person: int
    total: Any
    discount: Any = 0
    discount_label: str = ""
    order_source: Any = None
    address: dict = field(default_factory=dict)
    terms: Any = None


@dataclass(frozen=True)
class Estimate(Invoice):
    """عرض السعر: an invoice's fields, and the notes Daftra prints on it."""

    notes: str = ""


@dataclass(frozen=True)
class ExistingInvoice:
    """An invoice Daftra already has, which the Receipt after it pays (طلب تسديد مبلغ متبقي).

    The client is the invoice's own. name: how the form named it, for the error when it is gone.
    refuse_overpaying: a receipt for more than the invoice still owes is refused.
    """

    invoice_id: int
    name: str = ""
    refuse_overpaying: bool = True


@dataclass(frozen=True)
class InvoiceEmail:
    """The invoice emailed to the client by the portal, with its PDF and a link to see it.

    Sent by the portal, not by Daftra: Daftra sends nothing through the API (tried 2026-11-13).
    It never stops the approval — a failure is recorded, and it can be sent again.
    due_date: when the rest falls due; empty, the invoice's own date.
    """

    to: str
    client_name: str = ""
    due_date: str = ""


@dataclass(frozen=True)
class Receipt:
    """سند القبض, against the invoice made before it.

    method: the form's own word for it («تحويل بنكي»), turned into Daftra's key here, so an
    unknown one stops the approval before anything is sent.
    received_by: the Daftra staff member printed as its المستلم.
    notes: under the marker that finds it again.
    method_label, treasury_name, client_name: what the portal's own PDF of it prints.
    """

    amount: Any
    method: str
    treasury: Any
    date: str
    received_by: int
    reference: str = ""
    notes: str = ""
    treasury_name: str = ""
    client_name: str = ""

    def __post_init__(self):
        if money(self.amount) > 0 and not self.method_key:
            raise SyncError(f"طريقة الدفع «{self.method or '—'}» غير معروفة لدفترة.")

    @property
    def paid(self) -> Decimal:
        return money(self.amount)

    @property
    def method_key(self) -> str | None:
        return PAYMENT_METHOD_KEYS.get(self.method)


@dataclass(frozen=True)
class WorkOrder:
    """أمر الشغل, linked to the invoice made before it.

    title: what is installed and where; the engine adds the client's number, which exists only
    once the client is made.
    days: due this many days after it starts, which is the day it is approved.
    fields: its custom fields by name (work_order.WORK_ORDER_FIELDS), as Daftra's lists spell
    them. One left out is sent blank: Daftra empties any field a save leaves out.
    printed: the same values as the portal's PDF of it prints them.
    """

    title: str
    days: int
    description: str
    fields: dict
    printed: dict


__all__ = ["ClientRecord", "Estimate", "ExistingInvoice", "Invoice", "InvoiceEmail", "Receipt", "WorkOrder"]
