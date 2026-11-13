"""What طلب تعديل على طلب قائم asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, DISCOUNTED, HIDE, PAID, REQUIRED, REQUIRED_IF, SHOW, f, files,
                                    money, original_refs, shared, switched, yes_no)

[ORIGINAL_ORDER, ORIGINAL_INVOICE, WORK_ORDER] = original_refs()


def order_details(*, original_order, original_invoice, work_order, product_name, modified_items, before_change,
                  after_change, change_reason, execution_status, customer_approved, change_approved_by):
    return switched(
        "تفاصيل الطلب",
        (original_order, ORIGINAL_ORDER),
        (original_invoice, ORIGINAL_INVOICE),
        (work_order, WORK_ORDER),
        (product_name, f("product_name", "المنتج / الخدمة المرتبط بها التعديل", "product")),
        (modified_items, f("modified_items", "المطلوب تعديله", "multiselect",
                           options=["بيانات العميل", "العنوان", "المنتج", "الكمية", "اللون", "التصميم", "الكتابة",
                                    "السعر", "أخرى"])),
        (before_change, f("before_change", "البيانات أو المواصفات قبل التعديل", "textarea")),
        (after_change, f("after_change", "البيانات أو المواصفات المطلوبة بعد التعديل", "textarea")),
        (change_reason, f("change_reason", "سبب التعديل", "textarea")),
        (execution_status, f("execution_status", "حالة تنفيذ الطلب", "select",
                             options=["لم يبدأ", "قيد التنفيذ", "تم التنفيذ", "غير معروف"])),
        (customer_approved, yes_no("customer_approved", "هل العميل وافق على التعديل وتكلفته؟")),
        (change_approved_by, f("change_approved_by", "اسم المسؤول الذي اعتمد التعديل، إن تم اعتماده", "staff")),
    )


def amounts(*, value_change, total_before, total_amount, discount_amount, discount_approved_by, paid_amount,
            remaining_amount, remaining_due_date):
    """قيمة الطلب before and after the change. Every amount is typed: nothing here is worked out."""
    return switched(
        "قيمة الطلب",
        (value_change, f("value_change", "هل التعديل يغيّر قيمة الطلب؟", "select",
                         options=["زيادة", "تخفيض", "بدون تغيير", "تحتاج مراجعة"])),
        (total_before, money("total_before", "قيمة الطلب النهائية قبل التعديل")),
        (total_amount, money("total_amount", "قيمة الطلب النهائية بعد التعديل، شامل الضريبة والإضافات")),
        (discount_amount, money("discount_amount", "خصم إضافي مرتبط بالتعديل، إن وجد")),
        (discount_approved_by, f("discount_approved_by", "اسم الشخص الذي اعتمد الخصم", "staff")),
        (paid_amount, money("paid_amount", "المبلغ المدفوع فعليًا الآن")),
        (remaining_amount, money("remaining_amount", "المبلغ المتبقي بعد التعديل")),
        (remaining_due_date, f("remaining_due_date", "موعد سداد المتبقي، إن وجد", "date")),
    )


def attachments(*, invoice_image, design_image, inscription_file, payment_proof):
    return switched(
        "المرفقات",
        (invoice_image, files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت")),
        (design_image, files("design_image", "صورة التصميم أو المواصفات الجديدة، إن تنطبق")),
        (inscription_file, files("inscription_file", "صورة / ملف الكتابة الجديدة، إن وجدت")),
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجدت دفعة جديدة")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE,
    ),
    shared.address(
        category=SHOW, area=SHOW, emirate=SHOW, street=SHOW, house=SHOW, location_url=SHOW, coordinates=SHOW,
        title="عنوان الخدمة — إذا كان التعديل يخص العنوان",
    ),
    order_details(
        original_order=SHOW,
        original_invoice=SHOW,
        work_order=SHOW,
        product_name=REQUIRED,
        modified_items=REQUIRED,
        before_change=REQUIRED,
        after_change=REQUIRED,
        change_reason=REQUIRED,
        execution_status=REQUIRED,
        customer_approved=REQUIRED,
        change_approved_by=SHOW,
    ),
    amounts(
        value_change=REQUIRED,
        total_before=REQUIRED,
        total_amount=REQUIRED,
        discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED),
        paid_amount=REQUIRED,
        remaining_amount=REQUIRED,
        remaining_due_date=SHOW,
    ),
    shared.payment(
        payment_method=REQUIRED_IF(PAID), treasury=HIDE, payment_date=REQUIRED_IF(PAID),
        payment_reference=REQUIRED_IF(PAID), collector_name=REQUIRED_IF(CASH_PAYMENT),
        title="تفاصيل الدفعة — إن وُجدت دفعة جديدة",
    ),
    attachments(invoice_image=SHOW, design_image=SHOW, inscription_file=SHOW, payment_proof=REQUIRED_IF(PAID)),
    shared.notes(notes=SHOW),
]
