"""The fields of طلب إعادة تركيب, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    NOTES,
    PAID,
    address,
    attachments,
    client,
    f,
    files,
    money,
    original_refs,
    payment,
    request_info,
    section,
)

SECTIONS = [
    request_info("تاريخ الطلب"),
    client(True, "اسم العميل"),
    address("عنوان التركيب الجديد"),
    section(
        "تفاصيل الطلب",
        *original_refs(),
        f("product_name", "المنتج / الجهاز المطلوب إعادة تركيبه", "product", True),
        f("reinstall_reason", "سبب إعادة التركيب", "select", True,
          options=["نقل إلى عنوان جديد", "إعادة تركيب بعد صيانة", "تركيب سابق غير سليم", "أخرى"]),
        f("reason_details", "تفاصيل السبب", "textarea", True),
        f("current_location", "مكان الجهاز الحالي، إن اختلف عن العنوان الجديد"),
        f("preferred_date", "الموعد المفضل للتركيب", "date"),
        f("extra_works", "أعمال إضافية مطلوبة، إن وجدت (تمديدات، قاعدة، فك)", "textarea"),
    ),
    section(
        "قيمة الطلب",
        f("coverage", "تغطية الخدمة", "select", True, options=["مدفوعة", "مجانية / مشمولة", "تحتاج مراجعة"]),
        money("total_amount", "قيمة الخدمة شامل الضريبة", required_if={"field": "coverage", "equals": "مدفوعة"}),
        money("paid_amount", "المبلغ المدفوع فعليًا الآن"),
    ),
    payment(when=PAID),
    attachments(
        files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
        files("site_photos", "صور الموقع الجديد، إن توفرت"),
    ),
    NOTES,
]
