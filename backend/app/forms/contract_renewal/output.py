"""What approving طلب تجديد عقد الصيانة السنوي sends to Daftra: the client's details kept in step,
the one-line renewal invoice, and the receipt for what was paid.

The renewal is for a client Daftra already has: one the code and phone do not find is refused.
"""

from ...core.config import settings
from ...core.text import local_phone, squash
from ...modules.invoicing import (ClientRecord, Invoice, Receipt, approve, money, package_terms, sales_person,
                                  service_address)

# The description of the renewal invoice's one line, as staff write it by hand (e.g. invoice 06263)
RENEWAL_DESCRIPTION = "تجديد عقد الصيانه لمده عام مع تبديل فلاتر كل ثلاث اشهر"


def client(ctx):
    """العميل: one Daftra already has, kept in step with what the form says of it."""
    d = ctx.data
    return ClientRecord(
        phone=d.get("phone"),
        phone2=d.get("phone2"),
        client_code=d.get("client_code"),
        name=d.get("customer_name"),
        customer_type=d.get("customer_type"),
        gender=d.get("gender"),
        emirate=d.get("emirate"),
        area=d.get("area"),
        street=d.get("street"),
        house=d.get("house"),
        category=d.get("category"),
        category_name=d.get("category_name"),
        location_url=d.get("location_url"),
        coordinates=d.get("coordinates"),
        if_unknown=(f"لا يوجد في دفترة عميل بالرقم {local_phone(d.get('phone'))} أو الكود "
                    f"«{d.get('client_code') or '—'}». التجديد لعميل موجود فقط؛ أعد الطلب للموظف ليصحح بيانات العميل."),
        keep_in_step=True,
    )


def invoice(ctx):
    """الفاتورة: one line, the renewal, at the price the form settled on."""
    d = ctx.data
    return Invoice(
        items=[{
            "product_id": settings.daftra_renewal_product_id, "item": "exchange contract",
            "description": RENEWAL_DESCRIPTION,
            "unit_price": float(money(d.get("subtotal_amount"))), "quantity": 1,
            "tax1": settings.daftra_tax_id, "store_id": settings.daftra_store_id,
        }],
        sales_person=sales_person(ctx.request),
        date=d.get("request_date"),
        total=d.get("total_amount"),
        discount=d.get("discount_amount"),
        discount_label=d.get("discount_label") or "",
        order_source=d.get("order_source"),
        address=service_address(d),
        terms=package_terms(ctx),
    )


def receipt(ctx):
    """سند القبض for what was paid."""
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
