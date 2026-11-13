"""What طلب إعادة تركيب asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, HIDE, PAID, REQUIRED, REQUIRED_IF, SHOW, f, files, money,
                                    original_refs, shared, switched)

PAID_SERVICE = {"field": "coverage", "equals": "مدفوعة"}

[ORIGINAL_ORDER, ORIGINAL_INVOICE, WORK_ORDER] = original_refs()


def order_details(*, original_order, original_invoice, work_order, product_name, reinstall_reason, reason_details,
                  current_location, preferred_date, extra_works):
    return switched(
        "تفاصيل الطلب",
        (original_order, ORIGINAL_ORDER),
        (original_invoice, ORIGINAL_INVOICE),
        (work_order, WORK_ORDER),
        (product_name, f("product_name", "المنتج / الجهاز المطلوب إعادة تركيبه", "product")),
        (reinstall_reason, f("reinstall_reason", "سبب إعادة التركيب", "select",
                             options=["نقل إلى عنوان جديد", "إعادة تركيب بعد صيانة", "تركيب سابق غير سليم", "أخرى"])),
        (reason_details, f("reason_details", "تفاصيل السبب", "textarea")),
        (current_location, f("current_location", "مكان الجهاز الحالي، إن اختلف عن العنوان الجديد")),
        (preferred_date, f("preferred_date", "الموعد المفضل للتركيب", "date")),
        (extra_works, f("extra_works", "أعمال إضافية مطلوبة، إن وجدت (تمديدات، قاعدة، فك)", "textarea")),
    )


def amounts(*, coverage, total_amount, paid_amount):
    return switched(
        "قيمة الطلب",
        (coverage, f("coverage", "تغطية الخدمة", "select", options=["مدفوعة", "مجانية / مشمولة", "تحتاج مراجعة"])),
        (total_amount, money("total_amount", "قيمة الخدمة شامل الضريبة")),
        (paid_amount, money("paid_amount", "المبلغ المدفوع فعليًا الآن")),
    )


def attachments(*, payment_proof, site_photos):
    return switched(
        "المرفقات",
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجدت دفعة")),
        (site_photos, files("site_photos", "صور الموقع الجديد، إن توفرت")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الطلب"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    shared.address(
        category=REQUIRED, area=REQUIRED, emirate=REQUIRED, street=SHOW, house=SHOW, location_url=REQUIRED,
        coordinates=REQUIRED, title="عنوان التركيب الجديد",
    ),
    order_details(
        original_order=SHOW,
        original_invoice=SHOW,
        work_order=SHOW,
        product_name=REQUIRED,
        reinstall_reason=REQUIRED,
        reason_details=REQUIRED,
        current_location=SHOW,
        preferred_date=SHOW,
        extra_works=SHOW,
    ),
    amounts(coverage=REQUIRED, total_amount=REQUIRED_IF(PAID_SERVICE), paid_amount=SHOW),
    shared.payment(
        payment_method=REQUIRED_IF(PAID), treasury=HIDE, payment_date=REQUIRED_IF(PAID),
        payment_reference=REQUIRED_IF(PAID), collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(payment_proof=REQUIRED_IF(PAID), site_photos=SHOW),
    shared.notes(notes=SHOW),
]
