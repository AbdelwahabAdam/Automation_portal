"""What طلب إضافة على طلب قائم asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, DISCOUNTED, HIDE, INSCRIPTION, PAID, REQUIRED, REQUIRED_IF, SHOW,
                                    f, files, money, original_refs, shared, switched, yes_no)

WORK_STATUS = ["مطلوب تنفيذها", "تم تنفيذها", "تم تنفيذ جزء منها"]
WORK_STARTED = {"field": "addition_status", "in": WORK_STATUS[1:]}

[ORIGINAL_ORDER, ORIGINAL_INVOICE, WORK_ORDER] = original_refs()
[INSCRIPTION_TEXT, INSCRIPTION_PLACE] = INSCRIPTION


def order_details(*, original_order, original_invoice, work_order, product_name, addition_details, quantity_unit,
                  unit_price, specifications, inscription, inscription_place, customer_approved, addition_status,
                  execution_info):
    return switched(
        "تفاصيل الطلب",
        (original_order, ORIGINAL_ORDER),
        (original_invoice, ORIGINAL_INVOICE),
        (work_order, WORK_ORDER),
        (product_name, f("product_name", "المنتج / الخدمة المرتبط بها الإضافة", "product")),
        (addition_details, f("addition_details", "الإضافة المطلوبة بالتفصيل", "textarea")),
        (quantity_unit, f("quantity_unit", "الكمية / الطول والوحدة")),
        (unit_price, money("unit_price", "سعر الوحدة المتفق عليه، إن ينطبق")),
        (specifications, f("specifications", "اللون / المقاسات / المواصفات، إن تنطبق")),
        (inscription, INSCRIPTION_TEXT),
        (inscription_place, INSCRIPTION_PLACE),
        (customer_approved, yes_no("customer_approved", "هل العميل وافق على مواصفات الإضافة وتكلفتها؟")),
        (addition_status, f("addition_status", "حالة الإضافة", "select", options=WORK_STATUS)),
        (execution_info, f("execution_info", "تاريخ التنفيذ واسم الفني، إن تم")),
    )


def attachments(*, payment_proof, invoice_image, design_image, inscription_file):
    return switched(
        "المرفقات",
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجدت دفعة")),
        (invoice_image, files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت")),
        (design_image, files("design_image", "صورة التصميم أو الإضافة المتفق عليها، إن توفرت")),
        (inscription_file, files("inscription_file", "صورة / ملف الكتابة، إن وجدت")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE,
    ),
    shared.address(
        category=REQUIRED, area=REQUIRED, emirate=REQUIRED, street=SHOW, house=SHOW, location_url=REQUIRED,
        coordinates=REQUIRED,
    ),
    order_details(
        original_order=SHOW,
        original_invoice=SHOW,
        work_order=SHOW,
        product_name=REQUIRED,
        addition_details=REQUIRED,
        quantity_unit=REQUIRED,
        unit_price=SHOW,
        specifications=SHOW,
        inscription=SHOW,
        inscription_place=SHOW,
        customer_approved=REQUIRED,
        addition_status=REQUIRED,
        execution_info=REQUIRED_IF(WORK_STARTED),
    ),
    shared.amounts(
        subtotal_amount=HIDE, total_amount=REQUIRED, discount_label=HIDE, discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED), paid_amount=REQUIRED, remaining_amount=SHOW,
        remaining_due_date=SHOW,
        labels={"total_amount": "قيمة الإضافة النهائية بعد الخصم، شامل الضريبة",
                "discount_amount": "قيمة الخصم على الإضافة، إن وجد",
                "paid_amount": "المبلغ المدفوع فعليًا الآن مقابل الإضافة",
                "remaining_amount": "المبلغ المتبقي من قيمة الإضافة"},
    ),
    shared.payment(
        payment_method=REQUIRED_IF(PAID), treasury=HIDE, payment_date=REQUIRED_IF(PAID),
        payment_reference=REQUIRED_IF(PAID), collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(payment_proof=REQUIRED_IF(PAID), invoice_image=SHOW, design_image=SHOW, inscription_file=SHOW),
    shared.notes(notes=SHOW),
]
