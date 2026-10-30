"""The fields of تأكيد إتمام التركيب, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    NOTES,
    PAID,
    PAYMENT_METHODS,
    attachments,
    client,
    f,
    files,
    money,
    request_info,
    section,
    yes_no,
)

SECTIONS = [
    request_info("تاريخ الطلب"),
    client(True, "اسم العميل"),
    section(
        "تفاصيل التركيب",
        f("work_order", "رقم أمر الشغل", required=True),
        f("invoice_number", "رقم الفاتورة، إن توفر"),
        f("product_name", "المنتج الذي تم تركيبه", "product", True),
        f("installation_date", "تاريخ التركيب", "date", True, not_future=True),
        f("technician_name", "اسم الفني", "staff", required=True),
        f("installation_status", "حالة التركيب", "select", True, options=["تم بالكامل", "تم مع ملاحظات"]),
        f("issues", "الملاحظات على التركيب", "textarea",
          required_if={"field": "installation_status", "equals": "تم مع ملاحظات"}),
        yes_no("extra_work", "هل نُفذت أعمال إضافية؟"),
        f("extra_work_details", "تفاصيل الأعمال الإضافية", "textarea", required_if={"field": "extra_work", "equals": "نعم"}),
        yes_no("customer_signed", "هل وقّع العميل على استلام التركيب؟"),
    ),
    section(
        "التحصيل عند التركيب",
        money("paid_amount", "المبلغ المحصل عند التركيب، إن وجد"),
        f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, required_if=PAID),
        f("payment_reference", "رقم التحويل / السند الورقي", required_if=PAID),
    ),
    attachments(
        files("installation_photos", "صور التركيب بعد الانتهاء", True),
        files("signed_work_order", "صورة أمر الشغل الموقّع، إن توفرت"),
        files("payment_proof", "إثبات الدفع، إن وُجد تحصيل", required_if=PAID),
    ),
    NOTES,
]
