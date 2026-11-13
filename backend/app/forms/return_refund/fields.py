"""What طلب مرتجع ورد مبلغ asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH, HIDE, REQUIRED, REQUIRED_IF, SHOW, f, files, money, original_refs,
                                    shared, switched)

REFUND_METHODS = ["تحويل بنكي", CASH, "تابي", "تمارا", "أخرى"]

RECEIVED = {"field": "receipt_status", "equals": "تم الاستلام"}
DEDUCTED = {"field": "deduction_amount", "gt": 0}
REFUND_APPROVED = {"field": "approved_refund", "gt": 0}
REFUNDED = {"field": "refunded_amount", "gt": 0}
REFUNDED_IN_CASH = {"field": "refund_method", "equals": CASH}

[ORIGINAL_ORDER, ORIGINAL_INVOICE, WORK_ORDER] = original_refs()


def order_details(*, original_order, original_invoice, work_order, return_type, returned_items, returned_quantities,
                  return_reason, product_condition, receipt_status, receipt_date, received_by, return_approved_by):
    return switched(
        "تفاصيل الطلب",
        (original_order, ORIGINAL_ORDER),
        (original_invoice, ORIGINAL_INVOICE),
        (work_order, WORK_ORDER),
        (return_type, f("return_type", "نوع المرتجع", "select", options=["كامل الطلب", "جزء من الطلب"])),
        (returned_items, f("returned_items", "المنتج / الأصناف المطلوب إرجاعها", "textarea")),
        (returned_quantities, f("returned_quantities", "الكمية المرتجعة من كل صنف", "textarea")),
        (return_reason, f("return_reason", "سبب المرتجع", "textarea")),
        (product_condition, f("product_condition", "حالة المنتج وملاحظات عليه", "textarea")),
        (receipt_status, f("receipt_status", "حالة استلام المرتجع", "select", options=["لم يُستلم", "تم الاستلام"])),
        (receipt_date, f("receipt_date", "تاريخ الاستلام، إن تم", "date", not_future=True)),
        (received_by, f("received_by", "اسم الموظف الذي استلم المرتجع، إن تم", "staff")),
        (return_approved_by, f("return_approved_by", "اسم المسؤول الذي اعتمد المرتجع، إن تم اعتماده", "staff")),
    )


def amounts(*, invoice_total, total_paid, returned_value, deduction_amount, deduction_reason, approved_refund,
            refund_approved_by, refunded_amount, refund_remaining, refund_remaining_date):
    return switched(
        "قيمة الطلب",
        (invoice_total, money("invoice_total", "قيمة الطلب النهائية المسجلة على الفاتورة")),
        (total_paid, money("total_paid", "إجمالي المبلغ المدفوع على الطلب الأصلي")),
        (returned_value, money("returned_value", "قيمة الأصناف المرتجعة حسب الفاتورة")),
        (deduction_amount, money("deduction_amount", "قيمة أي استقطاع أو رسوم مرتبطة بالمرتجع، إن وجدت")),
        (deduction_reason, f("deduction_reason", "سبب الاستقطاع واسم المسؤول الذي اعتمده")),
        (approved_refund, money("approved_refund", "المبلغ المعتمد رده للعميل، إن تم تحديده")),
        (refund_approved_by, f("refund_approved_by", "اسم المسؤول الذي اعتمد مبلغ الرد", "staff")),
        (refunded_amount, money("refunded_amount", "المبلغ المردود فعليًا الآن")),
        (refund_remaining, f("refund_remaining", "المبلغ المتبقي من مبلغ الرد المعتمد", "number", money=True,
                             computed=["approved_refund", "refunded_amount"],
                             negative_message="المبلغ المردود أكبر من مبلغ الرد المعتمد")),
        (refund_remaining_date, f("refund_remaining_date", "موعد رد المتبقي، إن تم تحديده", "date")),
    )


def refund(*, refund_method, refund_date, refund_reference, refund_paid_by):
    return switched(
        "تفاصيل رد المبلغ — إن تم",
        (refund_method, f("refund_method", "طريقة رد المبلغ", "select", options=REFUND_METHODS)),
        (refund_date, f("refund_date", "تاريخ رد المبلغ", "date", not_future=True)),
        (refund_reference, f("refund_reference", "رقم التحويل / مرجع عملية الرد / السند")),
        (refund_paid_by, f("refund_paid_by", "اسم الموظف الذي سلّم المبلغ، في حالة الرد النقدي", "staff")),
    )


def attachments(*, invoice_image, product_photos, receipt_proof, refund_proof):
    return switched(
        "المرفقات",
        (invoice_image, files("invoice_image", "صورة الفاتورة الأصلية، إن توفرت")),
        (product_photos, files("product_photos", "صور المنتج المرتجع وحالته")),
        (receipt_proof, files("receipt_proof", "إثبات استلام المرتجع، إن تم")),
        (refund_proof, files("refund_proof", "إثبات رد المبلغ، إن تم")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE,
    ),
    shared.address(
        category=REQUIRED, area=REQUIRED, emirate=REQUIRED, street=SHOW, house=SHOW, location_url=REQUIRED,
        coordinates=REQUIRED, title="عنوان الخدمة / استلام المرتجع",
    ),
    order_details(
        original_order=SHOW,
        original_invoice=SHOW,
        work_order=SHOW,
        return_type=REQUIRED,
        returned_items=REQUIRED,
        returned_quantities=REQUIRED,
        return_reason=REQUIRED,
        product_condition=REQUIRED,
        receipt_status=REQUIRED,
        receipt_date=REQUIRED_IF(RECEIVED),
        received_by=REQUIRED_IF(RECEIVED),
        return_approved_by=SHOW,
    ),
    amounts(
        invoice_total=REQUIRED,
        total_paid=REQUIRED,
        returned_value=REQUIRED,
        deduction_amount=SHOW,
        deduction_reason=REQUIRED_IF(DEDUCTED),
        approved_refund=SHOW,
        refund_approved_by=REQUIRED_IF(REFUND_APPROVED),
        refunded_amount=REQUIRED,
        refund_remaining=SHOW,
        refund_remaining_date=SHOW,
    ),
    refund(
        refund_method=REQUIRED_IF(REFUNDED),
        refund_date=REQUIRED_IF(REFUNDED),
        refund_reference=REQUIRED_IF(REFUNDED),
        refund_paid_by=REQUIRED_IF(REFUNDED_IN_CASH),
    ),
    attachments(invoice_image=SHOW, product_photos=REQUIRED, receipt_proof=REQUIRED_IF(RECEIVED),
                refund_proof=REQUIRED_IF(REFUNDED)),
    shared.notes(notes=SHOW),
]
