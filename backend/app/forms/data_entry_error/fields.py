"""What تبليغ خطأ إدخال بيانات asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import HIDE, REQUIRED, SHOW, f, files, shared, switched


def error_details(*, document_type, document_number, error_field, wrong_value, correct_value, urgency):
    return switched(
        "تفاصيل الخطأ",
        (document_type, f("document_type", "المستند الذي فيه الخطأ", "select",
                          options=["فاتورة", "سند قبض", "عرض سعر", "أمر شغل", "بيانات عميل", "أخرى"])),
        (document_number, f("document_number", "رقم المستند")),
        (error_field, f("error_field", "البيان الخطأ (مثل: اسم العميل، المبلغ، التاريخ)")),
        (wrong_value, f("wrong_value", "القيمة المسجلة الخطأ", "textarea")),
        (correct_value, f("correct_value", "القيمة الصحيحة", "textarea")),
        (urgency, f("urgency", "الأولوية", "select", options=["عادي", "عاجل"])),
    )


def attachments(*, document_image, evidence):
    return switched(
        "المرفقات",
        (document_image, files("document_image", "صورة المستند الذي فيه الخطأ، إن توفرت")),
        (evidence, files("evidence", "ما يثبت القيمة الصحيحة، إن توفر")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ التبليغ"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=SHOW, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    error_details(document_type=REQUIRED, document_number=REQUIRED, error_field=REQUIRED, wrong_value=REQUIRED,
                  correct_value=REQUIRED, urgency=REQUIRED),
    attachments(document_image=SHOW, evidence=SHOW),
    shared.notes(notes=SHOW),
]
