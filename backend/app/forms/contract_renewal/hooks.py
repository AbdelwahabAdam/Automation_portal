"""What makes طلب تجديد عقد الصيانة السنوي different: what approving it creates in Daftra.

The existing client's category, the one-line renewal invoice, and its receipt.
Today's `sync_contract_renewal`.
"""

from ...core.config import settings
from ...core.text import local_phone
from ...core.errors import SyncError
from ...modules.invoicing import (ensure_invoice, finish, money, payment_inputs, reports_daftra_errors,
                            sales_person)
from ...modules.clients import existing_client_id, update_client

# The description of the renewal invoice's one line, as staff write it by hand (e.g. invoice 06263)
RENEWAL_DESCRIPTION = "تجديد عقد الصيانه لمده عام مع تبديل فلاتر كل ثلاث اشهر"


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db, reviewer = ctx.request, ctx.db, ctx.reviewer
    data = request.data
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    item = {
        "product_id": settings.daftra_renewal_product_id, "item": "exchange contract",
        "description": RENEWAL_DESCRIPTION,
        "unit_price": float(money(data.get("subtotal_amount"))), "quantity": 1,
        "tax1": settings.daftra_tax_id, "store_id": settings.daftra_store_id,
    }
    if request.daftra_client_id is None:
        found = existing_client_id(data, db)
        if found is None:
            raise SyncError(f"لا يوجد في دفترة عميل بالرقم {local_phone(data.get('phone'))} أو الكود "
                            f"«{data.get('client_code') or '—'}». التجديد لعميل موجود فقط؛ أعد الطلب للموظف ليصحح بيانات العميل.")
        request.save_document("client", found)
    update_client(request.daftra_client_id, data)
    invoice = ensure_invoice(request, [item], staff_id)
    return finish(request, invoice, paid, method, reviewer, db)
