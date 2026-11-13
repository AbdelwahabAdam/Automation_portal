"""What approving طلب صيانة وتبديل sends to Daftra: the client when new, the invoice of the chosen
items, and the receipt for what was paid.

Each function returns what goes into that document, field by field, or None when this request
has none. They are made in the order of DOCUMENTS, all built before any is sent.
"""

from ...core.config import settings
from ...core.text import squash
from ...modules.invoicing import (ClientRecord, Invoice, Receipt, approve, money, order_lines, package_terms,
                                  sales_person, service_address)

# Read below although this form does not ask them today. The shared code before output.py read
# them for every form, and a request written by an earlier version of a form may carry them, so
# they are read exactly as they were rather than dropped on a guess.
LEGACY_FIELDS = {"service_description", "payment_reference"}


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


def invoice(ctx):
    """الفاتورة of the parts and services chosen, each priced on its line."""
    d = ctx.data
    items = order_lines(ctx)
    # The general «service» item says what was done
    for item in items:
        if item["product_id"] == settings.daftra_inscription_product_id and d.get("service_description"):
            item["description"] = d["service_description"]
    return Invoice(
        items=items,
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
    """سند القبض for what was paid. None for a free visit."""
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
