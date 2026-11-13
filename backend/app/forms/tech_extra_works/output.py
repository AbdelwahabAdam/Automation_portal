"""What approving اعمال اضافية (قسم الفنيات) sends to Daftra: the invoice of the works done, and the
receipt for whatever was paid now.

The form asks for no address, so no client can be made here: it must be one Daftra already has,
and what the form says of it is not put on it.
"""

from ...core.text import local_phone, squash
from ...modules.invoicing import (ClientRecord, Invoice, Receipt, approve, money, order_lines, package_terms,
                                  sales_person, service_address)


def client(ctx):
    """العميل: found by code or phone, and refused when Daftra has neither."""
    d = ctx.data
    return ClientRecord(
        phone=d.get("phone"),
        phone2=d.get("phone2"),
        client_code=d.get("client_code"),
        name=d.get("customer_name"),
        customer_type=d.get("customer_type"),
        gender=d.get("gender"),
        if_unknown=(f"لا يوجد في دفترة عميل بالرقم {local_phone(d.get('phone'))} أو الكود "
                    f"«{d.get('client_code') or '—'}». الأعمال الإضافية لعميل مسجل فقط؛ "
                    "أعد الطلب للموظف ليصحح بيانات العميل."),
        keep_in_step=False,
    )


def invoice(ctx):
    """الفاتورة of the works chosen, each at this form's own price, «أخرى» as described on its line."""
    d = ctx.data
    return Invoice(
        items=order_lines(ctx),
        sales_person=sales_person(ctx.request),
        date=d.get("request_date"),
        total=d.get("total_amount"),
        order_source=d.get("order_source"),
        address=service_address(d),
        terms=package_terms(ctx),
    )


def receipt(ctx):
    """سند القبض for what was paid now. None when nothing was."""
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


DOCUMENTS = [client, invoice, receipt]
on_approve = approve(DOCUMENTS)
