"""What طلب تحويل عرض سعر إلى فاتورة asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, DISCOUNTED, HIDE, PAID, REQUIRED, REQUIRED_IF, SHOW, f, files,
                                    shared, switched, yes_no)

CUSTOMER_APPROVED = {"field": "customer_approved", "equals": "نعم"}
HAS_CHANGES = {"field": "has_changes", "equals": "نعم"}


def order_details(*, quotation_number, quotation_date, product_name, customer_approved, approval_date,
                  has_changes, change_details, conversion_approved_by, statement_needed):
    return switched(
        "تفاصيل الطلب",
        (quotation_number, f("quotation_number", "رقم عرض السعر المطلوب تحويله")),
        (quotation_date, f("quotation_date", "تاريخ عرض السعر", "date", not_future=True)),
        (product_name, f("product_name", "المنتج / الخدمة المرتبط بها العرض", "product")),
        (customer_approved, yes_no("customer_approved", "هل العميل وافق على عرض السعر؟")),
        (approval_date, f("approval_date", "تاريخ موافقة العميل، إن تم", "date", not_future=True)),
        (has_changes, yes_no("has_changes", "هل يوجد تغيير عن العرض؟")),
        (change_details, f("change_details", "تفاصيل التغيير، إن وجد", "textarea")),
        (conversion_approved_by, f("conversion_approved_by", "اسم المسؤول الذي اعتمد التحويل، إن تم", "staff")),
        (statement_needed, yes_no("statement_needed", "هل مطلوب إرسال كشف حساب؟")),
    )


def attachments(*, quotation_file, approval_proof, payment_proof, design_image):
    return switched(
        "المرفقات",
        (quotation_file, files("quotation_file", "عرض السعر المطلوب تحويله")),
        (approval_proof, files("approval_proof", "إثبات موافقة العميل، إن توفر")),
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجدت دفعة")),
        (design_image, files("design_image", "التصميم أو المواصفات المعدّلة، إن وجدت")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=SHOW, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل / الجهة المطلوب على الفاتورة"},
    ),
    shared.address(
        category=SHOW, area=SHOW, emirate=SHOW, street=SHOW, house=SHOW, location_url=SHOW, coordinates=SHOW,
        title="عنوان الخدمة — إذا تغيّر أو لم يُذكر في العرض",
    ),
    order_details(
        quotation_number=REQUIRED,
        quotation_date=REQUIRED,
        product_name=REQUIRED,
        customer_approved=REQUIRED,
        approval_date=REQUIRED_IF(CUSTOMER_APPROVED),
        has_changes=REQUIRED,
        change_details=REQUIRED_IF(HAS_CHANGES),
        conversion_approved_by=SHOW,
        statement_needed=REQUIRED,
    ),
    shared.amounts(
        subtotal_amount=HIDE, total_amount=REQUIRED, discount_label=HIDE, discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED), paid_amount=REQUIRED, remaining_amount=SHOW,
        remaining_due_date=SHOW, labels={"discount_amount": "خصم إضافي عن عرض السعر، إن وجد"},
    ),
    shared.payment(
        payment_method=REQUIRED_IF(PAID), treasury=HIDE, payment_date=REQUIRED_IF(PAID),
        payment_reference=REQUIRED_IF(PAID), collector_name=REQUIRED_IF(CASH_PAYMENT),
        title="تفاصيل الدفعة — إن وُجدت دفعة",
    ),
    attachments(quotation_file=REQUIRED, approval_proof=SHOW, payment_proof=REQUIRED_IF(PAID), design_image=SHOW),
    shared.notes(notes=SHOW),
]
