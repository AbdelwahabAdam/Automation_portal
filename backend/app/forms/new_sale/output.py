"""What approving طلب بيع لعميل جديد sends to Daftra: one function per document.

Each returns what goes into that document, field by field, or None when this request has none.
They are made in the order of DOCUMENTS; every one is built before any is sent, so a check one
makes (a product not linked to Daftra, an unknown payment method) stops the approval first.

What no form should repeat is the engine's (modules/invoicing): making each document once
however often the request is approved, is_offline, the store, the branch, the tax, checking
Daftra's total, and the PDFs.
"""

from ...core.text import squash
from ...modules.invoicing import (ClientRecord, Invoice, Receipt, WorkOrder, approve, installation_work_order,
                                  money, order_lines, package_terms, sales_person, service_address)


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
    """الفاتورة. No notes: Daftra prints an invoice's notes as its الشروط والأحكام."""
    d = ctx.data
    return Invoice(
        items=order_lines(ctx),                       # the products and packages, and each inscription
        sales_person=sales_person(ctx.request),       # بيعت بواسطة and أنشئ بواسطة
        date=d.get("request_date"),
        total=d.get("total_amount"),                  # what Daftra's total must come to
        discount=d.get("discount_amount"),
        discount_label=d.get("discount_label") or "",
        order_source=d.get("order_source"),
        address=service_address(d),                   # عنوان الخدمة, printed on the invoice
        terms=package_terms(ctx),                     # the packages' الشروط والأحكام
    )


def receipt(ctx):
    """سند القبض for what the customer paid now. None when nothing was paid."""
    d = ctx.data
    if money(d.get("paid_amount")) <= 0:
        return None
    return Receipt(
        amount=d.get("paid_amount"),
        method=d.get("payment_method") or "",
        treasury=d.get("treasury"),
        date=d.get("payment_date"),
        reference=d.get("payment_reference") or "",
        received_by=sales_person(ctx.request),        # المستلم: the salesperson, not the approving manager
        treasury_name=d.get("treasury_name") or "",
        client_name=squash(d.get("customer_name")),
    )


def work_order(ctx):
    """أمر الشغل for the installation, when the form asked for one."""
    d = ctx.data
    if d.get("create_work_order") != "نعم":
        return None
    # Worked out from the order lines as the floor writes them; any of it can be changed here
    made = installation_work_order(ctx.request, ctx.db)
    return WorkOrder(
        title=made.title,                             # what and where; the client's code is added
        days=int(d.get("installation_days") or 20),   # due this many days after approval
        description=made.description,                 # ملاحظات, then رقم مسؤول اخر
        fields={
            "installation_accessories": made.fields["installation_accessories"],
            "product_image": made.fields["product_image"],
            "available_colors": made.fields["available_colors"],
            "cover_back": made.fields["cover_back"],
            "base_color": made.fields["base_color"],
            "location": made.fields["location"],
            "design_version": made.fields["design_version"],
            "sales_person": made.fields["sales_person"],
            "cooler_color": made.fields["cooler_color"],
            "w_direction": made.fields["w_direction"],
            "front_design": made.fields["front_design"],
            "inscription": made.fields["inscription"],
            "plate_color": made.fields["plate_color"],
            "extensions": made.fields["extensions"],
            "device": made.fields["device"],          # نوع الجهاز, on Daftra's own print
            "address": made.fields["address"],        # العنوان, the request's own, not the client's
        },
        printed=made.printed,                         # the same values, as the portal's PDF prints them
    )


DOCUMENTS = [client, invoice, receipt, work_order]
on_approve = approve(DOCUMENTS)
