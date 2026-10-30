"""The fields of فتح بلاغ صيانة وأعطال, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, address, attachments, client, f, files, request_info, section

SECTIONS = [
    request_info("تاريخ البلاغ"),
    client(False, "اسم العميل"),
    address(),
    section(
        "تفاصيل البلاغ",
        f("device_type", "الجهاز / البرادة", required=True),
        f("related_number", "رقم العقد أو الفاتورة المرتبطة، إن توفر"),
        f("problem", "وصف العطل كما ذكره العميل", "textarea", True),
        f("coverage", "تغطية الإصلاح", "select", True, options=["ضمان", "عقد صيانة", "مدفوع", "غير معروف"]),
        f("urgency", "الأولوية", "select", True, options=["عادي", "عاجل", "طارئ"]),
        f("preferred_date", "الموعد المفضل للزيارة، إن وجد", "date"),
    ),
    attachments(files("fault_media", "صور / فيديو العطل، إن توفرت")),
    NOTES,
]
