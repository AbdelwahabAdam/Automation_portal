"""What تأكيد إتمام التركيب asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (HIDE, PAID, PAYMENT_METHODS, REQUIRED, REQUIRED_IF, SHOW, f, files, money, shared,
                                    switched, yes_no)

WITH_ISSUES = {"field": "installation_status", "equals": "تم مع ملاحظات"}
EXTRA_WORK_DONE = {"field": "extra_work", "equals": "نعم"}


def installation_details(*, work_order, invoice_number, product_name, installation_date, technician_name,
                         installation_status, issues, extra_work, extra_work_details, customer_signed):
    return switched(
        "تفاصيل التركيب",
        (work_order, f("work_order", "رقم أمر الشغل")),
        (invoice_number, f("invoice_number", "رقم الفاتورة، إن توفر")),
        (product_name, f("product_name", "المنتج الذي تم تركيبه", "product")),
        (installation_date, f("installation_date", "تاريخ التركيب", "date", not_future=True)),
        (technician_name, f("technician_name", "اسم الفني", "staff")),
        (installation_status, f("installation_status", "حالة التركيب", "select",
                                options=["تم بالكامل", "تم مع ملاحظات"])),
        (issues, f("issues", "الملاحظات على التركيب", "textarea")),
        (extra_work, yes_no("extra_work", "هل نُفذت أعمال إضافية؟")),
        (extra_work_details, f("extra_work_details", "تفاصيل الأعمال الإضافية", "textarea")),
        (customer_signed, yes_no("customer_signed", "هل وقّع العميل على استلام التركيب؟")),
    )


def collection(*, paid_amount, payment_method, payment_reference):
    return switched(
        "التحصيل عند التركيب",
        (paid_amount, money("paid_amount", "المبلغ المحصل عند التركيب، إن وجد")),
        (payment_method, f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS)),
        (payment_reference, f("payment_reference", "رقم التحويل / السند الورقي")),
    )


def attachments(*, installation_photos, signed_work_order, payment_proof):
    return switched(
        "المرفقات",
        (installation_photos, files("installation_photos", "صور التركيب بعد الانتهاء")),
        (signed_work_order, files("signed_work_order", "صورة أمر الشغل الموقّع، إن توفرت")),
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجد تحصيل")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الطلب"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    installation_details(
        work_order=REQUIRED,
        invoice_number=SHOW,
        product_name=REQUIRED,
        installation_date=REQUIRED,
        technician_name=REQUIRED,
        installation_status=REQUIRED,
        issues=REQUIRED_IF(WITH_ISSUES),
        extra_work=REQUIRED,
        extra_work_details=REQUIRED_IF(EXTRA_WORK_DONE),
        customer_signed=REQUIRED,
    ),
    collection(paid_amount=SHOW, payment_method=REQUIRED_IF(PAID), payment_reference=REQUIRED_IF(PAID)),
    attachments(installation_photos=REQUIRED, signed_work_order=SHOW, payment_proof=REQUIRED_IF(PAID)),
    shared.notes(notes=SHOW),
]
