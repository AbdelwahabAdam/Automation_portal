"""What طلب بيع - دفع إلكتروني asks: طلب بيع لعميل جديد's own sections, with these differences.

- بيانات العميل asks every client for an email (not only a new one): the invoice is emailed to it,
  and it is put on the client in Daftra.
- قيمة الطلب starts المبلغ المدفوع فعليًا الآن at 0, and takes 0: the client pays the invoice later.
- المرفقات asks for nothing.
- التركيب وأمر الشغل is gone: the work order is made from the request once it is paid
  («إنشاء أمر الشغل», which asks for مدة التركيب then).

The sections only طلب بيع has (تفاصيل الطلب, المرفقات) are its functions, called here with this
form's own switches: a change to what طلب بيع asks does not change this form unless made here too.
"""

from ...modules.form_engine import (CASH_PAYMENT, DISCOUNTED, HAS_REMAINDER, HIDE, REQUIRED, REQUIRED_IF, SHOW,
                                    f, shared)
from ..new_sale import fields as sale

SECTIONS = [
    shared.request_info(
        request_date=REQUIRED,
        employee_name=SHOW,
        order_source=REQUIRED,
        source=HIDE,
    ),
    shared.client(
        phone=REQUIRED,
        phone2=SHOW,
        client_code=SHOW,
        customer_name=REQUIRED,
        customer_type=SHOW,
        gender=SHOW,
        email=REQUIRED,                     # every client: the invoice is sent to it
        labels={"email": "البريد الإلكتروني للعميل"},
        placeholders={"email": "تُرسل إليه الفاتورة ورابط مشاهدتها"},
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
    sale.order_details(
        order_lines=REQUIRED,
        package_quantity=SHOW,
        cooler_color=REQUIRED,
        cover_color=SHOW,
        plate_color=SHOW,
        front_design=SHOW,
        w_direction=SHOW,
        cover_back=SHOW,
        design_version=SHOW,
        base_color=SHOW,
        inscription=SHOW,
        inscription_price=REQUIRED_IF(sale.HAS_INSCRIPTION),
        manufacturing_notes=SHOW,
        installation_accessories=SHOW,
        item_price=REQUIRED,
        work_description=REQUIRED,
    ),
    shared.amounts(
        subtotal_amount=SHOW,
        total_amount=SHOW,
        discount_label=REQUIRED_IF(DISCOUNTED),
        discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED),
        paid_amount=REQUIRED,
        remaining_amount=SHOW,
        remaining_due_date=REQUIRED_IF(HAS_REMAINDER),
        must_pay=False,                     # the client pays the invoice later
        paid_default="0",
    ),
    shared.payment(
        payment_method=REQUIRED,
        treasury=REQUIRED,
        payment_date=REQUIRED,
        payment_reference=REQUIRED,
        collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    sale.attachments(
        payment_proof=SHOW,
        design_image=SHOW,
        inscription_file=SHOW,
    ),
    shared.notes(notes=SHOW),
]

# What the request asks for when its work order is made, after it is paid («إنشاء أمر الشغل»)
INSTALLATION_DAYS = f("installation_days", "مدة التركيب (بالأيام)", "number", True, integer=True, min=1,
                      max=sale.MAX_INSTALLATION_DAYS, placeholder="مثال: 15 أو 20", unit="يومًا")
