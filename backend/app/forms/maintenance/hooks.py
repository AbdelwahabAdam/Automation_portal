"""What makes طلب صيانة وتبديل different: what approving it creates in Daftra.

The client when new, the invoice of the chosen items, and its receipt. Today's `sync_maintenance`.
"""

from ...core.config import settings
from ...modules.invoicing import (ensure_invoice, finish, invoice_items, payment_inputs,
                            reports_daftra_errors, sales_person)
from ...modules.clients import client_id, update_client


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db = ctx.request, ctx.db
    data = request.data
    items = invoice_items(data, db)
    # The general «service» item says what was done
    for item in items:
        if item["product_id"] == settings.daftra_inscription_product_id and data.get("service_description"):
            item["description"] = data["service_description"]
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    if request.daftra_client_id is None:
        request.save_document("client", client_id(data, db))
    update_client(request.daftra_client_id, data)
    invoice = ensure_invoice(request, items, staff_id)
    return finish(request, invoice, paid, method, db)
