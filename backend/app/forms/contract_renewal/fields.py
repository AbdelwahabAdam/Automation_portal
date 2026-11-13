"""What طلب تجديد عقد الصيانة السنوي asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, DISCOUNTED, HAS_REMAINDER, HIDE, REQUIRED, REQUIRED_IF, SHOW, f,
                                    files, shared, switched)

# The renewal price a طلب تجديد عقد الصيانة السنوي starts from; the salesperson can change it
RENEWAL_PRICE = 1680


# ---------- this form's own sections ----------

def order_details(*, cooler_type, cooler_notes):
    return switched(
        "تفاصيل الطلب",
        (cooler_type, f("cooler_type", "نوع البرادة")),
        (cooler_notes, f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea")),
        note="الخدمة: تجديد عقد لمدة سنة، تبديل الفلاتر كل 3 شهور مع صيانة البرادة.",
    )


def attachments(*, payment_proof):
    return switched("المرفقات", (payment_proof, files("payment_proof", "إثبات الدفع")))


# ---------- the form ----------

SECTIONS = [
    shared.request_info(
        request_date=REQUIRED,
        employee_name=SHOW,
        order_source=REQUIRED,
        source=HIDE,
        labels={"request_date": "تاريخ الطلب"},
    ),
    shared.client(
        phone=REQUIRED,
        phone2=SHOW,
        client_code=SHOW,
        customer_name=REQUIRED,
        customer_type=SHOW,
        gender=SHOW,
        email=HIDE,                          # the client is one Daftra already has
        note="التجديد لعميل موجود في دفترة فقط؛ ابحث عنه برقم الهاتف أو الكود.",
    ),
    shared.address(
        category=REQUIRED,
        area=REQUIRED,
        emirate=REQUIRED,
        street=SHOW,
        house=SHOW,
        location_url=REQUIRED,
        coordinates=REQUIRED,
    ),
    order_details(
        cooler_type=REQUIRED,
        cooler_notes=SHOW,
    ),
    shared.amounts(
        subtotal_amount=REQUIRED,            # the renewal price, typed, starting at RENEWAL_PRICE
        total_amount=SHOW,
        discount_label=REQUIRED_IF(DISCOUNTED),
        discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED),
        paid_amount=REQUIRED,
        remaining_amount=SHOW,
        remaining_due_date=REQUIRED_IF(HAS_REMAINDER),
        must_pay=True,
        price_default=RENEWAL_PRICE,
        labels={"subtotal_amount": "سعر تجديد العقد قبل الخصم، شامل الضريبة",
                "total_amount": "قيمة الطلب النهائية بعد الخصم، شامل الضريبة"},
    ),
    shared.payment(
        payment_method=REQUIRED,
        treasury=REQUIRED,
        payment_date=REQUIRED,
        payment_reference=REQUIRED,
        collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(payment_proof=REQUIRED),
    shared.notes(notes=SHOW),
]
