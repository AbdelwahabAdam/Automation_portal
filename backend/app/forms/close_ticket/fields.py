"""What إغلاق بلاغ صيانة وأعطال asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, HIDE, PAID, REQUIRED, REQUIRED_IF, SHOW, f, files, money, shared,
                                    switched)

NEEDS_ANOTHER_VISIT = {"field": "resolution", "equals": "يحتاج زيارة أخرى"}
PAID_REPAIR = {"field": "coverage", "equals": "مدفوع"}


def closing_details(*, ticket_number, visit_date, technician_name, resolution, work_details, parts, follow_up_date):
    return switched(
        "تفاصيل الإغلاق",
        (ticket_number, f("ticket_number", "رقم البلاغ / الطلب الأصلي")),
        (visit_date, f("visit_date", "تاريخ الزيارة", "date", not_future=True)),
        (technician_name, f("technician_name", "اسم الفني", "staff")),
        (resolution, f("resolution", "نتيجة الزيارة", "select",
                       options=["تم الإصلاح", "تم استبدال قطع", "يحتاج زيارة أخرى", "تعذر الإصلاح"])),
        (work_details, f("work_details", "الأعمال المنفذة بالتفصيل", "textarea")),
        (parts, f("parts", "القطع المستبدلة وكمياتها، إن وجدت", "textarea")),
        (follow_up_date, f("follow_up_date", "موعد الزيارة التالية", "date")),
    )


def amounts(*, coverage, total_amount, paid_amount):
    return switched(
        "قيمة الطلب",
        (coverage, f("coverage", "تغطية الإصلاح", "select", options=["مشمول بعقد أو ضمان", "مدفوع"])),
        (total_amount, money("total_amount", "قيمة الإصلاح شامل الضريبة")),
        (paid_amount, money("paid_amount", "المبلغ المدفوع فعليًا الآن")),
    )


def attachments(*, after_photos, payment_proof):
    return switched(
        "المرفقات",
        (after_photos, files("after_photos", "صور بعد الإصلاح، إن توفرت")),
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجدت دفعة")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الإغلاق"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    closing_details(
        ticket_number=REQUIRED,
        visit_date=REQUIRED,
        technician_name=REQUIRED,
        resolution=REQUIRED,
        work_details=REQUIRED,
        parts=SHOW,
        follow_up_date=REQUIRED_IF(NEEDS_ANOTHER_VISIT),
    ),
    amounts(coverage=REQUIRED, total_amount=REQUIRED_IF(PAID_REPAIR), paid_amount=SHOW),
    shared.payment(
        payment_method=REQUIRED_IF(PAID), treasury=HIDE, payment_date=REQUIRED_IF(PAID),
        payment_reference=REQUIRED_IF(PAID), collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(after_photos=SHOW, payment_proof=REQUIRED_IF(PAID)),
    shared.notes(notes=SHOW),
]
