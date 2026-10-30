"""What makes طلب عرض سعر different: what approving it creates in Daftra.

The client when new, and the estimate (عرض سعر) with its lines — and nothing else. An estimate is
an offer: Daftra gives it its own numbering, takes no payment against it and posts nothing to the
accounts, so there is no receipt here and no work order. Its PDF is kept on the request, which is
what gets sent to the customer.
"""

from ...modules.clients import client_id, update_client
from ...modules.invoicing import (ensure_estimate, invoice_items, reports_daftra_errors,
                                  sales_person, save_estimate_pdf)


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db = ctx.request, ctx.db
    data = request.data
    # Everything that can be checked here is, before anything is sent
    items = invoice_items(data, db)
    staff_id = sales_person(request)
    if request.daftra_client_id is None:
        request.save_document("client", client_id(data, db))
    update_client(request.daftra_client_id, data)
    estimate = ensure_estimate(request, items, staff_id, notes=payment_note(data))
    return {"daftra_estimate_no": request.daftra_estimate_no,
            "estimate_pdf_saved": save_estimate_pdf(request, estimate, db)}


def payment_note(data: dict) -> str:
    """How the offer would be paid, printed on it — the one thing تفاصيل الدفعة is for here."""
    method = (data.get("payment_method") or "").strip()
    return f"طريقة الدفع: {method}" if method else ""
