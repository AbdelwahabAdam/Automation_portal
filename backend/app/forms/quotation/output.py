"""What approving طلب عرض سعر sends to Daftra: the client when new, and the estimate — nothing else.

An estimate (عرض السعر) is an offer: Daftra numbers it on its own, takes no payment against it
and posts nothing to the accounts, so there is no receipt here and no work order. Its PDF is kept
on the request, which is what is sent to the customer. It is never emailed by Daftra.
"""

from ...modules.invoicing import (ClientRecord, Estimate, approve, form_notes, order_lines, package_terms,
                                  sales_person, service_address)


def client(ctx):
    """العميل: found by code or phone, made when new, and kept in step with what the form says."""
    d = ctx.data
    return ClientRecord(
        phone=d.get("phone"),
        phone2=d.get("phone2"),
        client_code=d.get("client_code"),
        name=d.get("customer_name"),
        customer_type=d.get("customer_type"),
        gender=d.get("gender"),
        email=d.get("email"),
        emirate=d.get("emirate"),
        area=d.get("area"),
        street=d.get("street"),
        house=d.get("house"),
        category=d.get("category"),
        category_name=d.get("category_name"),
        location_url=d.get("location_url"),
        coordinates=d.get("coordinates"),
        if_unknown="create",
        keep_in_step=True,
    )


def estimate(ctx):
    """عرض السعر, with the products and packages as the invoice would have them."""
    d = ctx.data
    return Estimate(
        items=order_lines(ctx),
        sales_person=sales_person(ctx.request),
        date=d.get("request_date"),
        total=d.get("total_amount"),
        discount=d.get("discount_amount"),
        discount_label=d.get("discount_label") or "",
        order_source=d.get("order_source"),
        address=service_address(d),
        terms=package_terms(ctx),
        # How it would be paid, then the salesperson's ملاحظات
        notes=form_notes(d, payment_note(d)),
    )


def payment_note(data: dict) -> str:
    """How the offer would be paid, printed on it — the one thing تفاصيل الدفعة is for here."""
    method = (data.get("payment_method") or "").strip()
    return f"طريقة الدفع: {method}" if method else ""


DOCUMENTS = [client, estimate]
on_approve = approve(DOCUMENTS)
