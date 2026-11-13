"""What approving طلب بيع - دفع إلكتروني sends to Daftra, and its two actions once approved.

Approving makes the client and the invoice, as طلب بيع does, then emails the invoice to the
client and leaves the request «بانتظار الدفع». From there, once the client has paid,
«إنشاء أمر الشغل» makes the work order and ends it; or «إعادة إرسال الفاتورة» sends the email again.

Nothing is usually paid on approval (المبلغ المدفوع starts at 0), so usually no receipt is made.
The payment is checked by hand for now.
"""

from ...core.errors import ExternalFailure, Invalid
from ...core.text import squash
from ...modules import notifications
from ...modules.invoicing import (ClientRecord, Invoice, InvoiceEmail, Receipt, WorkOrder, approve, get_invoice,
                                  installation_work_order, make_work_order, money, order_lines, package_terms,
                                  reports_daftra_errors, sales_person, send_invoice_email, service_address)
from .fields import INSTALLATION_DAYS

AWAITING_PAYMENT = "awaiting_payment"


def client(ctx):
    """العميل: found by code or phone, made when new, and given the email the invoice goes to."""
    d = ctx.data
    return ClientRecord(
        phone=d.get("phone"),
        phone2=d.get("phone2"),
        client_code=d.get("client_code"),
        name=d.get("customer_name"),
        customer_type=d.get("customer_type"),
        gender=d.get("gender"),
        email=d.get("email"),
        emirate=d.get("emirate"),
        area=d.get("area"),
        street=d.get("street"),
        house=d.get("house"),
        category=d.get("category"),
        category_name=d.get("category_name"),
        location_url=d.get("location_url"),
        coordinates=d.get("coordinates"),
        if_unknown="create",
        keep_in_step=True,
    )


def invoice(ctx):
    """الفاتورة, as طلب بيع makes it."""
    d = ctx.data
    return Invoice(
        items=order_lines(ctx),
        sales_person=sales_person(ctx.request),
        date=d.get("request_date"),
        total=d.get("total_amount"),
        discount=d.get("discount_amount"),
        discount_label=d.get("discount_label") or "",
        order_source=d.get("order_source"),
        address=service_address(d),
        terms=package_terms(ctx),
    )


def receipt(ctx):
    """سند القبض, only if something was paid already. None otherwise, which is the usual case."""
    d = ctx.data
    if money(d.get("paid_amount")) <= 0:
        return None
    return Receipt(
        amount=d.get("paid_amount"),
        method=d.get("payment_method") or "",
        treasury=d.get("treasury"),
        date=d.get("payment_date"),
        reference=d.get("payment_reference") or "",
        received_by=sales_person(ctx.request),
        treasury_name=d.get("treasury_name") or "",
        client_name=squash(d.get("customer_name")),
    )


def invoice_email(ctx):
    """The invoice, emailed by the portal to the address on the form, with what is due."""
    d = ctx.data
    return InvoiceEmail(
        to=d.get("email") or "",
        client_name=squash(d.get("customer_name")),
        due_date=d.get("remaining_due_date") or "",
    )


def work_order(ctx):
    """أمر الشغل, made by «إنشاء أمر الشغل» once the client has paid, as طلب بيع makes it."""
    d = ctx.data
    made = installation_work_order(ctx.request, ctx.db)
    return WorkOrder(
        title=made.title,
        days=int(d.get("installation_days") or 20),   # asked by the action, and kept on the request
        description=made.description,
        fields={
            "installation_accessories": made.fields["installation_accessories"],
            "product_image": made.fields["product_image"],
            "available_colors": made.fields["available_colors"],
            "cover_back": made.fields["cover_back"],
            "base_color": made.fields["base_color"],
            "location": made.fields["location"],
            "design_version": made.fields["design_version"],
            "sales_person": made.fields["sales_person"],
            "cooler_color": made.fields["cooler_color"],
            "w_direction": made.fields["w_direction"],
            "front_design": made.fields["front_design"],
            "inscription": made.fields["inscription"],
            "plate_color": made.fields["plate_color"],
            "extensions": made.fields["extensions"],
        },
        printed=made.printed,
    )


DOCUMENTS = [client, invoice, receipt, invoice_email]
on_approve = approve(DOCUMENTS)


# ---------- after approval ----------

def installation_days(values: dict) -> int:
    raw = str(values.get(INSTALLATION_DAYS["name"]) or "").strip()
    days = int(raw) if raw.isdigit() else 0
    if not INSTALLATION_DAYS["min"] <= days <= INSTALLATION_DAYS["max"]:
        raise Invalid(fields={INSTALLATION_DAYS["name"]:
                              f"اكتب عدد أيام بين {INSTALLATION_DAYS['min']} و{INSTALLATION_DAYS['max']}"})
    return days


@reports_daftra_errors
def create_work_order(ctx, values: dict) -> dict:
    """The client has paid: the installation work order, due after مدة التركيب."""
    request = ctx.request
    days = installation_days(values)
    # Kept on the request, so the work order (and its PDF) say the same as a طلب بيع's would
    request.data = {**request.data, "installation_days": days, "create_work_order": "نعم"}
    invoice_row = get_invoice(request.daftra_invoice_id)
    pdf_saved, fields_saved, staff_assigned = make_work_order(request, invoice_row, ctx.reviewer, ctx.db,
                                                              work_order(ctx))
    return {"installation_days": days, "daftra_work_order_no": request.daftra_work_order_no,
            "work_order_pdf_saved": pdf_saved, "work_order_fields_saved": fields_saved,
            "work_order_staff_assigned": staff_assigned, "note": f"مدة التركيب {days} يومًا"}


def resend_invoice_email(ctx, values: dict) -> dict:
    """The invoice email again, with what is still due today."""
    try:
        to = send_invoice_email(ctx.request, invoice_email(ctx))
    except notifications.MailError as error:
        raise ExternalFailure(f"تعذر إرسال البريد إلى العميل: {error}")
    return {"invoice_emailed_to": to, "note": to}
