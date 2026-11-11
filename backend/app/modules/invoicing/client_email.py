"""The invoice emailed to the client, for a form whose client pays it later (طلب بيع - دفع إلكتروني).

Sent by the portal, not by Daftra: Daftra's own «send to client» works only for a user logged in
to it, never through the API. The link is the invoice's preview (`invoice_html_url`), which opens
without logging in. Daftra's payment page (`/client/invoices/pay/<id>`) asks the client to log in
whatever hash it is given, so it is not offered.
"""

from decimal import Decimal

from ...core.config import UPLOAD_DIR
from ...core.text import day_month_year, squash
from .. import notifications
from .common import INVOICE_ATTACHMENT_FIELD, money
from .invoice import get_invoice


def amount(value) -> str:
    """1250 -> «1,250», 1250.5 -> «1,250.50», as the client reads it beside «د.إ»."""
    figure = f"{money(value):,.2f}"
    return figure[:-3] if figure.endswith(".00") else figure


def invoice_pdf(request) -> list[tuple[str, bytes, str]]:
    """The invoice's PDF as the approval saved it on the request, to attach; none if it was not."""
    saved = next((a for a in request.attachments if a.field == INVOICE_ATTACHMENT_FIELD), None)
    # The request's own id: one saved in this same approval is not flushed yet, so has none of its own
    path = saved and UPLOAD_DIR / str(request.id) / saved.stored_name
    if path is None or not path.exists():
        return []
    return [(saved.filename, path.read_bytes(), "application/pdf")]


def email_invoice_to_client(request) -> str:
    """Emails the request's invoice to the email on the request, with what is still due today.
    Returns the address it went to; raises notifications.MailError if it could not be sent."""
    to = str(request.data.get("email") or "").strip()
    if not to:
        raise notifications.MailError("لا يوجد بريد إلكتروني للعميل في الطلب")
    invoice = get_invoice(request.daftra_invoice_id)
    due_on = request.data.get("remaining_due_date") or invoice.get("date") or ""
    unpaid = invoice.get("summary_unpaid")
    message = notifications.compose(
        "invoice_to_client",
        invoice_no=invoice.get("no") or request.daftra_invoice_no or "",
        client_name=squash(request.data.get("customer_name")) or "عميلنا العزيز",
        due_date=day_month_year(str(due_on)) if due_on else "—",
        total=amount(invoice.get("summary_total")),
        due=amount(unpaid if unpaid is not None else Decimal(invoice.get("summary_total") or 0)),
        link=invoice.get("invoice_html_url") or "",
    )
    notifications.send(to, *message, attachments=invoice_pdf(request))
    return to
