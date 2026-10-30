"""What makes طلب تسديد مبلغ متبقي different: the one check the field rules cannot express,
and what approving it creates in Daftra (a receipt on the chosen invoice).

Today the check is hard-coded in the shared `requests_api.apply_action`, and the Daftra side is
`sync_balance_payment`.
"""

from ...core.errors import SyncError
from ...modules.invoicing import (TOTAL_TOLERANCE, finish, get_invoice, money, payment_inputs, payment_of,
                            reports_daftra_errors)
from ...integrations.daftra import NotFound

# Daftra rounds each line's tax on its own, so an amount may be a hair over the unpaid total
PAID_TOLERANCE = 0.005


def validate(data: dict, ctx) -> dict:
    """What is paid now cannot be more than the chosen invoice still has to pay."""
    invoices = ctx.choices.get("daftra_client_invoice") or []
    chosen = next((invoice for invoice in invoices if invoice["id"] == data.get("invoice")), None)
    if chosen and data.get("paid_amount", 0) > chosen["unpaid"] + PAID_TOLERANCE:
        return {"paid_amount": f"المبلغ أكبر من المتبقي على الفاتورة ({chosen['unpaid']:,.2f} درهم)"}
    return {}


@reports_daftra_errors
def on_approve(ctx) -> dict:
    request, db, reviewer = ctx.request, ctx.db, ctx.reviewer
    data = request.data
    paid, method = payment_inputs(data)
    request.save_document("invoice", int(data["invoice"]))
    try:
        invoice = get_invoice(request.daftra_invoice_id)
    except NotFound:
        raise SyncError(f"الفاتورة {data.get('invoice_name') or data['invoice']} لم تعد موجودة في دفترة. "
                        "أعد الطلب للموظف ليختار الفاتورة الصحيحة.")
    request.save_document("client", int(invoice["client_id"]))
    request.save_document("invoice", int(data["invoice"]), invoice.get("no") or "")
    unpaid = money(invoice.get("summary_unpaid"))
    if request.daftra_payment_id is None and not payment_of(request, invoice) and paid > unpaid + TOTAL_TOLERANCE:
        raise SyncError(f"المبلغ المدفوع {paid} أكبر من المتبقي على الفاتورة {request.daftra_invoice_no} ({unpaid}). "
                        "أعد الطلب للموظف ليصحح المبلغ.")
    return finish(request, invoice, paid, method, reviewer, db)
