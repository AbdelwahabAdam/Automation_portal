"""The fields of تبليغ خطأ إدخال بيانات, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import NOTES, attachments, client, f, files, request_info, section

SECTIONS = [
    request_info("تاريخ التبليغ"),
    client(False, "اسم العميل"),
    section(
        "تفاصيل الخطأ",
        f("document_type", "المستند الذي فيه الخطأ", "select", True,
          options=["فاتورة", "سند قبض", "عرض سعر", "أمر شغل", "بيانات عميل", "أخرى"]),
        f("document_number", "رقم المستند", required=True),
        f("error_field", "البيان الخطأ (مثل: اسم العميل، المبلغ، التاريخ)", required=True),
        f("wrong_value", "القيمة المسجلة الخطأ", "textarea", True),
        f("correct_value", "القيمة الصحيحة", "textarea", True),
        f("urgency", "الأولوية", "select", True, options=["عادي", "عاجل"]),
    ),
    attachments(
        files("document_image", "صورة المستند الذي فيه الخطأ، إن توفرت"),
        files("evidence", "ما يثبت القيمة الصحيحة، إن توفر"),
    ),
    NOTES,
]
