"""What makes طلب بيع لعميل جديد different: what approving it creates in Daftra.

The client when new, the invoice with its lines, the receipt (سند قبض) for what the customer
paid now, and the installation work order when asked for. Today's `sync_new_sale`.
"""

from ...modules.invoicing import (ensure_invoice, ensure_work_order, finish, invoice_items, payment_inputs,
                            reports_daftra_errors, sales_person)
from ...modules.clients import client_id, update_client


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
    update_client(request.daftra_client_id, data)
    invoice = ensure_invoice(request, items, staff_id)
    summary = finish(request, invoice, paid, method, reviewer, db)
    if data.get("create_work_order") == "نعم":
        summary["work_order_pdf_saved"], summary["work_order_fields_saved"] = ensure_work_order(
            request, invoice, reviewer, db)
        summary["daftra_work_order_no"] = request.daftra_work_order_no
    return summary
