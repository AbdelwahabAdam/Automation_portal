"""Creating in Daftra what an approved request stands for:

- طلب بيع لعميل جديد: the client when new, the invoice with its lines, the receipt (سند قبض)
  for what the customer paid now, and the installation work order when asked for;
- طلب تجديد عقد الصيانة السنوي: the existing client's category, the one-line renewal invoice, and
  its receipt;
- طلب صيانة وتبديل: the client when new, the invoice of the chosen items, and its receipt;
- طلب تسديد مبلغ متبقي: a receipt on one of the client's invoices.

Each step keeps the id it got on the request before the next one starts. Approving again after a
failure therefore carries on from the step that failed. If an id was lost (e.g. the response never
arrived), the invoice is found again by its po_number and the payment by its notes, both
"PORTAL-<request id>", so neither is created twice.

The steps live in client.py, invoice.py (with the receipt) and work_order.py; common.py has
what they share.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..daftra import NotFound
from ..text import local_phone
from ..models import Request, User
from ..text import day_month_year
from .client import client_id, existing_client_id, held_custom_fields, known_client, save_address, update_client
from .common import TOTAL_TOLERANCE, SyncError, money, payment_inputs, reports_daftra_errors, sales_person
from .invoice import ensure_invoice, finish, get_invoice, invoice_items, payment_of
from .work_order import ensure_work_order

__all__ = ["SyncError", "existing_client_id", "held_custom_fields", "known_client", "save_address", "sync"]

# The description of the renewal invoice's one line, as staff write it by hand (e.g. invoice 06263)
RENEWAL_DESCRIPTION = "تجديد عقد الصيانه لمده عام مع تبديل فلاتر كل ثلاث اشهر"


def sync(request: Request, db: Session, reviewer: User) -> dict:
    """Creates in Daftra whatever the approved request needs that does not exist yet. Returns a
    summary for the audit log; raises SyncError, leaving on the request the ids of what was created.
    The approving reviewer is the receipt's المستلم."""
    summary = SYNCS[request.form_type](request, db, reviewer)
    request.daftra_error = None
    request.daftra_synced_at = datetime.now(timezone.utc)
    return summary


@reports_daftra_errors
def sync_new_sale(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    # Everything that can be checked here is, before anything is sent
    items = invoice_items(data, db)
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    if request.daftra_client_id is None:
        request.daftra_client_id = client_id(data, db)
    update_client(request)
    invoice = ensure_invoice(request, items, staff_id)
    summary = finish(request, invoice, paid, method, reviewer, db)
    if data.get("create_work_order") == "نعم":
        summary["work_order_pdf_saved"], summary["work_order_fields_saved"] = ensure_work_order(request, invoice, reviewer, db)
        summary["daftra_work_order_no"] = request.daftra_work_order_no
    return summary


@reports_daftra_errors
def sync_contract_renewal(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    item = {
        "product_id": settings.daftra_renewal_product_id, "item": "exchange contract", "description": RENEWAL_DESCRIPTION,
        "unit_price": float(money(data.get("subtotal_amount"))), "quantity": 1,
        "tax1": settings.daftra_tax_id, "store_id": settings.daftra_store_id,
    }
    if request.daftra_client_id is None:
        found = existing_client_id(data, db)
        if found is None:
            raise SyncError(f"لا يوجد في دفترة عميل بالرقم {local_phone(data.get('phone'))} أو الكود "
                            f"«{data.get('client_code') or '—'}». التجديد لعميل موجود فقط؛ أعد الطلب للموظف ليصحح بيانات العميل.")
        request.daftra_client_id = found
    update_client(request)
    invoice = ensure_invoice(request, [item], staff_id)
    return finish(request, invoice, paid, method, reviewer, db)


@reports_daftra_errors
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
    if request.daftra_client_id is None:
        request.daftra_client_id = client_id(data, db)
    update_client(request)
    invoice = ensure_invoice(request, items, staff_id, notes=notes)
    return finish(request, invoice, paid, method, reviewer, db)


@reports_daftra_errors
def sync_balance_payment(request: Request, db: Session, reviewer: User) -> dict:
    data = request.data
    paid, method = payment_inputs(data)
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
    return finish(request, invoice, paid, method, reviewer, db)


SYNCS = {"new_sale": sync_new_sale, "contract_renewal": sync_contract_renewal, "balance_payment": sync_balance_payment,
         "maintenance": sync_maintenance}
