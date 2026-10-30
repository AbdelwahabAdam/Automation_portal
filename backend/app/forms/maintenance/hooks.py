"""What makes طلب صيانة وتبديل different: what approving it creates in Daftra.

The client when new, the invoice of the chosen items, and its receipt. Today's `sync_maintenance`.
"""

from ...core.config import settings
from ...core.text import day_month_year
from ...modules.invoicing import (ensure_invoice, finish, invoice_items, payment_inputs,
                            reports_daftra_errors, sales_person)
from ...modules.clients import client_id, update_client


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db, reviewer = ctx.request, ctx.db, ctx.reviewer
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
        request.save_document("client", client_id(data, db))
    update_client(request.daftra_client_id, data)
    invoice = ensure_invoice(request, items, staff_id, notes=notes)
    return finish(request, invoice, paid, method, reviewer, db)
