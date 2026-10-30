"""The fields of إغلاق بلاغ صيانة وأعطال, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, PAID, attachments, client, f, files, money, payment, request_info, section

SECTIONS = [
    request_info("تاريخ الإغلاق"),
    client(True, "اسم العميل"),
    section(
        "تفاصيل الإغلاق",
        f("ticket_number", "رقم البلاغ / الطلب الأصلي", required=True),
        f("visit_date", "تاريخ الزيارة", "date", True, not_future=True),
        f("technician_name", "اسم الفني", "staff", required=True),
        f("resolution", "نتيجة الزيارة", "select", True,
          options=["تم الإصلاح", "تم استبدال قطع", "يحتاج زيارة أخرى", "تعذر الإصلاح"]),
        f("work_details", "الأعمال المنفذة بالتفصيل", "textarea", True),
        f("parts", "القطع المستبدلة وكمياتها، إن وجدت", "textarea"),
        f("follow_up_date", "موعد الزيارة التالية", "date", required_if={"field": "resolution", "equals": "يحتاج زيارة أخرى"}),
    ),
    section(
        "قيمة الطلب",
        f("coverage", "تغطية الإصلاح", "select", True, options=["مشمول بعقد أو ضمان", "مدفوع"]),
        money("total_amount", "قيمة الإصلاح شامل الضريبة", required_if={"field": "coverage", "equals": "مدفوع"}),
        money("paid_amount", "المبلغ المدفوع فعليًا الآن"),
    ),
    payment(when=PAID),
    attachments(
        files("after_photos", "صور بعد الإصلاح، إن توفرت"),
        files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
    ),
    NOTES,
]
