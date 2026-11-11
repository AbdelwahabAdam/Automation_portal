"""What makes طلب بيع - دفع إلكتروني different: approving it makes the client and the invoice, as
طلب بيع does, then emails the invoice to the client and leaves the request «بانتظار الدفع».
From there, once the client has paid, «إنشاء أمر الشغل» makes the work order and ends it; or
«إعادة إرسال الفاتورة» sends the email again.

Nothing is paid on approval (المبلغ المدفوع is usually 0), so no receipt is made. The payment is
checked by hand for now.
"""

from ...core.errors import ExternalFailure, Invalid
from ...modules import notifications, requests
from ...modules.clients import client_id, update_client
from ...modules.invoicing import (email_invoice_to_client, ensure_invoice, ensure_work_order, finish,
                                  get_invoice, invoice_items, payment_inputs, reports_daftra_errors,
                                  sales_person)
from .definition import INSTALLATION_DAYS

AWAITING_PAYMENT = "awaiting_payment"


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db, reviewer = ctx.request, ctx.db, ctx.reviewer
    data = request.data
    # Everything that can be checked here is, before anything is sent
    items = invoice_items(data, db)
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    if request.daftra_client_id is None:
        request.save_document("client", client_id(data, db))
    # The email typed on the form is put on the client too
    update_client(request.daftra_client_id, data, db)
    invoice = ensure_invoice(request, items, staff_id)
    summary = finish(request, invoice, paid, method, db)
    # The approval stands even if the email does not go: it can be sent again from the request
    try:
        to = email_invoice_to_client(request)
        requests.record_event(db, request, reviewer, "invoice_emailed", to)
        summary["invoice_emailed_to"] = to
    except notifications.MailError as error:
        summary["invoice_email_failed"] = str(error)
    return summary


def installation_days(values: dict) -> int:
    raw = str(values.get(INSTALLATION_DAYS["name"]) or "").strip()
    days = int(raw) if raw.isdigit() else 0
    if not INSTALLATION_DAYS["min"] <= days <= INSTALLATION_DAYS["max"]:
        raise Invalid(fields={INSTALLATION_DAYS["name"]:
                              f"اكتب عدد أيام بين {INSTALLATION_DAYS['min']} و{INSTALLATION_DAYS['max']}"})
    return days


@reports_daftra_errors
def create_work_order(ctx, values: dict) -> dict:
    """The client has paid: the installation work order, due after مدة التركيب, as طلب بيع makes it."""
    request = ctx.request
    days = installation_days(values)
    # Kept on the request, so the work order (and its PDF) say the same as a طلب بيع's would
    request.data = {**request.data, "installation_days": days, "create_work_order": "نعم"}
    invoice = get_invoice(request.daftra_invoice_id)
    pdf_saved, fields_saved, staff_assigned = ensure_work_order(request, invoice, ctx.reviewer, ctx.db)
    return {"installation_days": days, "daftra_work_order_no": request.daftra_work_order_no,
            "work_order_pdf_saved": pdf_saved, "work_order_fields_saved": fields_saved,
            "work_order_staff_assigned": staff_assigned, "note": f"مدة التركيب {days} يومًا"}


def resend_invoice_email(ctx, values: dict) -> dict:
    """The invoice email again, with what is still due today."""
    try:
        to = email_invoice_to_client(ctx.request)
    except notifications.MailError as error:
        raise ExternalFailure(f"تعذر إرسال البريد إلى العميل: {error}")
    return {"invoice_emailed_to": to, "note": to}
