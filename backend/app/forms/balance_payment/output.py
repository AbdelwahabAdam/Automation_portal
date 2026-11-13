"""What approving طلب تسديد مبلغ متبقي sends to Daftra: a receipt on the invoice the form chose.

No invoice is made and no client: both are the chosen invoice's own. The receipt carries the
salesperson's ملاحظات, since there is no invoice of this request's to carry them.
"""

from ...core.text import squash
from ...modules.invoicing import ExistingInvoice, Receipt, approve, form_notes, sales_person


def invoice(ctx):
    """The invoice being paid, which must still owe at least what is paid now."""
    d = ctx.data
    return ExistingInvoice(invoice_id=int(d["invoice"]), name=d.get("invoice_name") or "", refuse_overpaying=True)


def receipt(ctx):
    """سند القبض on that invoice."""
    d = ctx.data
    return Receipt(
        amount=d.get("paid_amount"),
        method=d.get("payment_method") or "",
        treasury=d.get("treasury"),
        date=d.get("payment_date"),
        reference=d.get("payment_reference") or "",
        received_by=sales_person(ctx.request),
        notes=form_notes(d),                          # under the marker that finds it again
        treasury_name=d.get("treasury_name") or "",
        client_name=squash(d.get("customer_name")),
    )


DOCUMENTS = [invoice, receipt]
on_approve = approve(DOCUMENTS)
