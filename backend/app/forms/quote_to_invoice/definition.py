"""The fields of طلب تحويل عرض سعر إلى فاتورة, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    NOTES,
    PAID,
    address,
    amounts,
    attachments,
    client,
    f,
    files,
    payment,
    request_info,
    section,
    yes_no,
)

SECTIONS = [
    request_info(),
    client(False, "اسم العميل / الجهة المطلوب على الفاتورة"),
    address("عنوان الخدمة — إذا تغيّر أو لم يُذكر في العرض", required=False),
    section(
        "تفاصيل الطلب",
        f("quotation_number", "رقم عرض السعر المطلوب تحويله", required=True),
        f("quotation_date", "تاريخ عرض السعر", "date", True, not_future=True),
        f("product_name", "المنتج / الخدمة المرتبط بها العرض", "product", True),
        yes_no("customer_approved", "هل العميل وافق على عرض السعر؟"),
        f("approval_date", "تاريخ موافقة العميل، إن تم", "date", not_future=True,
          required_if={"field": "customer_approved", "equals": "نعم"}),
        yes_no("has_changes", "هل يوجد تغيير عن العرض؟"),
        f("change_details", "تفاصيل التغيير، إن وجد", "textarea",
          required_if={"field": "has_changes", "equals": "نعم"}),
        f("conversion_approved_by", "اسم المسؤول الذي اعتمد التحويل، إن تم", "staff"),
        yes_no("statement_needed", "هل مطلوب إرسال كشف حساب؟"),
    ),
    amounts(discount_label="خصم إضافي عن عرض السعر، إن وجد"),
    payment("تفاصيل الدفعة — إن وُجدت دفعة", when=PAID),
    attachments(
        files("quotation_file", "عرض السعر المطلوب تحويله", True),
        files("approval_proof", "إثبات موافقة العميل، إن توفر"),
        files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
        files("design_image", "التصميم أو المواصفات المعدّلة، إن وجدت"),
    ),
    NOTES,
]
