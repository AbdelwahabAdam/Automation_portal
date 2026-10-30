"""The fields of طلب تجديد عقد الصيانة السنوي, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    NOTES,
    address,
    amounts,
    attachments,
    client,
    f,
    files,
    payment,
    request_info,
    section,
)

# Choices only this form offers
# The renewal price a طلب تجديد عقد الصيانة السنوي starts from; the salesperson can change it
RENEWAL_PRICE = 1680

SECTIONS = [
    request_info("تاريخ الطلب", invoiced=True),
    {**client(False), "note": "التجديد لعميل موجود في دفترة فقط؛ ابحث عنه برقم الهاتف أو الكود."},
    address(),
    section(
        "تفاصيل الطلب",
        f("cooler_type", "نوع البرادة", required=True),
        f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea"),
        note="الخدمة: تجديد عقد لمدة سنة، تبديل الفلاتر كل 3 شهور مع صيانة البرادة.",
    ),
    amounts(total_label="قيمة الطلب النهائية بعد الخصم، شامل الضريبة", must_pay=True, invoiced=True,
            price_label="سعر تجديد العقد قبل الخصم، شامل الضريبة", price_default=RENEWAL_PRICE),
    payment(invoiced=True),
    attachments(files("payment_proof", "إثبات الدفع", True)),
    NOTES,
]
