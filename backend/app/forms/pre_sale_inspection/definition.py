"""The fields of طلب معاينة قبل البيع, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, address, attachments, client, f, files, request_info, section

SECTIONS = [
    request_info("تاريخ الطلب"),
    client(False, "اسم العميل / الجهة"),
    address("عنوان المعاينة"),
    section(
        "تفاصيل الطلب",
        f("site_type", "نوع الموقع", "select", True,
          options=["منزل", "مسجد", "مدرسة", "مغسلة سيارات", "جمعية خيرية", "شركة", "أخرى"]),
        f("product_name", "المنتج المبدئي المهتم به العميل، إن وجد", "product"),
        f("inspection_purpose", "المطلوب من المعاينة", "textarea", True),
        f("preferred_date", "الموعد المفضل للمعاينة", "date"),
        f("preferred_time", "الوقت المفضل", "select", options=["صباحًا", "ظهرًا", "مساءً"]),
        f("site_contact", "اسم ورقم الشخص المسؤول في الموقع، إن اختلف عن العميل"),
    ),
    attachments(files("site_photos", "صور الموقع، إن توفرت")),
    NOTES,
]
