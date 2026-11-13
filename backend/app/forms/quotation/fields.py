"""What طلب عرض سعر asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds

The same shape as طلب بيع لعميل جديد, because the two are quoted and sold from the same catalog:
the products and packages are picked and priced the same way. What it does not ask for is what a
sale has and an offer has not — the amount paid, what is left, and the work order, none of which
an estimate carries in Daftra.
"""

from ...modules.form_engine import (
    CASH_PAYMENT,
    COLORS,
    DISCOUNTED,
    HIDE,
    INSCRIPTION,
    MAX_PACKAGE_QUANTITY,
    NEW_CLIENT,
    NO_INSCRIPTION,
    OPEN_PRICE_FIELDS,
    PACKAGE_COLOR_FAMILIES,
    REQUIRED,
    REQUIRED_IF,
    SHOW,
    f,
    files,
    money,
    shared,
    switched,
    switched_fields,
)

HAS_INSCRIPTION = {"field": "inscription", "not_in": NO_INSCRIPTION}

[ITEM_PRICE, WORK_DESCRIPTION] = OPEN_PRICE_FIELDS


# ---------- this form's own sections ----------

def order_details(*, order_lines, package_quantity, cooler_color, cover_color, inscription, inscription_price,
                  dimensions, special_requirements, item_price, work_description):
    """تفاصيل الطلب: what is being quoted. Every switch but order_lines is a field of each line."""
    lines = switched_fields(
        (package_quantity, f("package_quantity", "الكمية (عدد الباقات)", "number", integer=True, min=1,
                             max=MAX_PACKAGE_QUANTITY, package_only=True, stepper=True)),
        # Often what the quotation is sent to find out, so its label says it may not be known yet
        (cooler_color, f("cooler_color", "لون البرادة، إن تم تحديده", "select", options=COLORS)),
        (cover_color, f("cover_color", "لون الغطاء، إن يوجد", "package_color", optional=True,
                        families=[{**family, "colors": [shown for shown, _ in family["colors"]]}
                                  for family in PACKAGE_COLOR_FAMILIES])),
        (inscription, INSCRIPTION[0]),
        (inscription_price, money("inscription_price", "سعر الكتابة، شامل الضريبة (درهم)", charge=True,
                                  beside="inscription")),
        (dimensions, f("dimensions", "المقاسات المطلوبة، إن تنطبق")),
        (special_requirements, f("special_requirements", "مواصفات أو متطلبات خاصة", "textarea")),
        # A product with no fixed price: its price and text, typed on its own line
        (item_price, ITEM_PRICE),
        (work_description, WORK_DESCRIPTION),
    )
    return switched(
        "تفاصيل الطلب",
        (order_lines, f("order_lines", "المنتجات والباقات", "order_lines", subtotal_field="subtotal_amount",
                        line_fields=lines)),
        note="الأسعار من الكتالوج؛ عدّلها على السطر إن كان العرض بسعر آخر.",
    )


def attachments(*, payment_proof, design_image, inscription_file, specification_file):
    return switched(
        "المرفقات",
        (payment_proof, files("payment_proof", "إثبات الدفع، إن سبق الدفع")),
        (design_image, files("design_image", "صورة المنتج أو التصميم المطلوب، إن توفرت")),
        (inscription_file, files("inscription_file", "صورة / ملف الكتابة، إن وجدت")),
        (specification_file, files("specification_file", "ملف مواصفات أو طلب الجهة، إن وجد")),
    )


# ---------- the form ----------

SECTIONS = [
    shared.request_info(
        request_date=REQUIRED,
        employee_name=SHOW,
        order_source=REQUIRED,
        source=HIDE,
        labels={"request_date": "تاريخ الطلب"},
    ),
    shared.client(
        phone=REQUIRED,
        phone2=SHOW,
        client_code=SHOW,
        customer_name=REQUIRED,
        customer_type=SHOW,
        gender=SHOW,
        email=NEW_CLIENT(SHOW),
        labels={"customer_name": "اسم العميل / الجهة المطلوب على عرض السعر"},
    ),
    shared.address(
        category=REQUIRED,
        area=REQUIRED,
        emirate=REQUIRED,
        street=SHOW,
        house=SHOW,
        location_url=REQUIRED,
        coordinates=REQUIRED,
    ),
    order_details(
        order_lines=REQUIRED,
        package_quantity=SHOW,
        cooler_color=SHOW,
        cover_color=SHOW,
        inscription=SHOW,
        inscription_price=REQUIRED_IF(HAS_INSCRIPTION),
        dimensions=SHOW,
        special_requirements=SHOW,
        item_price=REQUIRED,
        work_description=REQUIRED,
    ),
    # Nothing is paid against an offer, and Daftra records no payment on an estimate
    shared.amounts(
        subtotal_amount=SHOW,
        total_amount=SHOW,
        discount_label=REQUIRED_IF(DISCOUNTED),
        discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED),
        paid_amount=HIDE,
        remaining_amount=HIDE,
        remaining_due_date=HIDE,
        labels={"total_amount": "قيمة العرض النهائية بعد الخصم، شامل الضريبة والإضافات",
                "discount_amount": "قيمة الخصم المقترح، إن وجد"},
    ),
    # How it would be paid, if the customer accepts: only طريقة الدفع is demanded
    shared.payment(
        payment_method=REQUIRED,
        treasury=HIDE,
        payment_date=SHOW,
        payment_reference=SHOW,
        collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(
        payment_proof=SHOW,
        design_image=SHOW,
        inscription_file=SHOW,
        specification_file=SHOW,
    ),
    shared.notes(notes=SHOW),
]
