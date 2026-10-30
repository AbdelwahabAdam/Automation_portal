"""The fields of طلب عرض سعر, as sections (form_engine has the building blocks).

The same shape as طلب بيع لعميل جديد, because the two are quoted and sold from the same catalog:
the products and packages are picked the same way, and priced the same way. What it does not ask
for is everything a sale has and an offer has not — the amount paid, what is left, and the work
order, none of which an estimate carries in Daftra.
"""

from ...modules.form_engine import (
    COLORS,
    INSCRIPTION,
    MAX_PACKAGE_QUANTITY,
    NOTES,
    NO_INSCRIPTION,
    PACKAGE_COLOR_FAMILIES,
    address,
    amounts,
    attachments,
    client,
    f,
    files,
    money,
    payment,
    request_info,
    section,
)

HAS_INSCRIPTION = {"field": "inscription", "not_in": NO_INSCRIPTION}

SECTIONS = [
    request_info("تاريخ الطلب", invoiced=True),
    client(False, "اسم العميل / الجهة المطلوب على عرض السعر", creates_client=True),
    address(),
    section(
        "تفاصيل الطلب",
        f("order_lines", "المنتجات والباقات", "order_lines", True, subtotal_field="subtotal_amount", line_fields=[
            f("package_quantity", "الكمية (عدد الباقات)", "number", integer=True, min=1, max=MAX_PACKAGE_QUANTITY,
              package_only=True, stepper=True),
            # Not required, unlike طلب بيع: what colour the customer wants is often what the
            # quotation is sent to find out
            f("cooler_color", "لون البرادة، إن تم تحديده", "select", options=COLORS),
            f("cover_color", "لون الغطاء، إن يوجد", "package_color", optional=True,
              families=[{**family, "colors": [shown for shown, _ in family["colors"]]} for family in PACKAGE_COLOR_FAMILIES]),
            INSCRIPTION[0],
            money("inscription_price", "سعر الكتابة، شامل الضريبة (درهم)", required_if=HAS_INSCRIPTION,
                  charge=True, beside="inscription"),
            f("dimensions", "المقاسات المطلوبة، إن تنطبق"),
            f("special_requirements", "مواصفات أو متطلبات خاصة", "textarea"),
        ]),
        note="الأسعار من الكتالوج؛ عدّلها على السطر إن كان العرض بسعر آخر.",
    ),
    # No «المبلغ المدفوع» and no «المتبقي»: nothing is paid against an offer, and Daftra records
    # no payment on an estimate
    amounts(total_label="قيمة العرض النهائية بعد الخصم، شامل الضريبة والإضافات",
            discount_label="قيمة الخصم المقترح، إن وجد", auto_total=True, invoiced=True, paid=False),
    # How it would be paid, if the customer accepts. Only طريقة الدفع is asked for.
    payment("تفاصيل الدفعة", details=False),
    attachments(
        files("payment_proof", "إثبات الدفع، إن سبق الدفع"),
        files("design_image", "صورة المنتج أو التصميم المطلوب، إن توفرت"),
        files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
        files("specification_file", "ملف مواصفات أو طلب الجهة، إن وجد"),
    ),
    NOTES,
]
