"""The fields of طلب إضافة على طلب قائم, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    INSCRIPTION,
    NOTES,
    PAID,
    address,
    amounts,
    attachments,
    client,
    f,
    files,
    money,
    original_refs,
    payment,
    request_info,
    section,
    yes_no,
)

# Choices only this form offers
WORK_STATUS = ["مطلوب تنفيذها", "تم تنفيذها", "تم تنفيذ جزء منها"]

WORK_STARTED = WORK_STATUS[1:]

SECTIONS = [
    request_info(),
    client(True),
    address(),
    section(
        "تفاصيل الطلب",
        *original_refs(),
        f("product_name", "المنتج / الخدمة المرتبط بها الإضافة", "product", True),
        f("addition_details", "الإضافة المطلوبة بالتفصيل", "textarea", True),
        f("quantity_unit", "الكمية / الطول والوحدة", required=True),
        money("unit_price", "سعر الوحدة المتفق عليه، إن ينطبق"),
        f("specifications", "اللون / المقاسات / المواصفات، إن تنطبق"),
        *INSCRIPTION,
        yes_no("customer_approved", "هل العميل وافق على مواصفات الإضافة وتكلفتها؟"),
        f("addition_status", "حالة الإضافة", "select", True, options=WORK_STATUS),
        f("execution_info", "تاريخ التنفيذ واسم الفني، إن تم",
          required_if={"field": "addition_status", "in": WORK_STARTED}),
    ),
    amounts(
        total_label="قيمة الإضافة النهائية بعد الخصم، شامل الضريبة",
        discount_label="قيمة الخصم على الإضافة، إن وجد",
        paid_label="المبلغ المدفوع فعليًا الآن مقابل الإضافة",
        remaining_label="المبلغ المتبقي من قيمة الإضافة",
    ),
    payment(when=PAID),
    attachments(
        files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
        files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت"),
        files("design_image", "صورة التصميم أو الإضافة المتفق عليها، إن توفرت"),
        files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
    ),
    NOTES,
]
