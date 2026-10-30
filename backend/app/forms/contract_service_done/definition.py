"""The fields of تأكيد إنجاز خدمة مشمولة بالعقد, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, attachments, client, f, files, request_info, section

SECTIONS = [
    request_info("تاريخ الطلب"),
    client(True, "اسم العميل"),
    section(
        "تفاصيل الخدمة",
        f("contract_number", "رقم العقد / الفاتورة", required=True),
        f("visit_number", "رقم الزيارة في العقد", "select", True,
          options=["الزيارة الأولى", "الزيارة الثانية", "الزيارة الثالثة", "الزيارة الرابعة", "زيارة إضافية"]),
        f("services_done", "الخدمات المنفذة", "multiselect", True,
          options=["تبديل فلاتر", "صيانة البرادة", "تنظيف", "فحص"]),
        f("service_date", "تاريخ التنفيذ", "date", True, not_future=True),
        f("technician_name", "اسم الفني", "staff", required=True),
        f("parts", "القطع والفلاتر المستبدلة وكمياتها", "textarea"),
        f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea"),
        f("next_visit_date", "موعد الزيارة القادمة، إن تحدد", "date"),
    ),
    attachments(
        files("service_photos", "صور قبل وبعد الخدمة، إن توفرت"),
        files("signed_report", "تقرير الزيارة الموقّع، إن توفر"),
    ),
    NOTES,
]
