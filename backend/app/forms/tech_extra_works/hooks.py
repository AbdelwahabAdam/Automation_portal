"""What makes اعمال اضافية (قسم الفنيات) different: what approving it creates in Daftra.

The invoice of the works done, and its receipt for whatever was paid now. The form asks for no
address, so the client cannot be created here — it must be one Daftra already has.
Today's `sync_tech_extra_works`.
"""

from ...core.errors import SyncError
from ...core.text import local_phone
from ...modules.clients import existing_client_id
from ...modules.invoicing import (ensure_invoice, finish, invoice_items, payment_inputs,
                                  reports_daftra_errors, sales_person)


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db = ctx.request, ctx.db
    data = request.data
    items = invoice_items(data, db)
    staff_id = sales_person(request)
    paid, method = payment_inputs(data)
    if request.daftra_client_id is None:
        found = existing_client_id(data, db)
        if found is None:
            raise SyncError(f"لا يوجد في دفترة عميل بالرقم {local_phone(data.get('phone'))} أو الكود "
                            f"«{data.get('client_code') or '—'}». الأعمال الإضافية لعميل مسجل فقط؛ "
                            "أعد الطلب للموظف ليصحح بيانات العميل.")
        request.save_document("client", found)
    invoice = ensure_invoice(request, items, staff_id)
    return finish(request, invoice, paid, method, db)
