"""What تسجيل تحصيل نقدي بواسطة الفني asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import CASH, HIDE, REQUIRED, SHOW, f, files, money, shared, switched


def order_details(*, invoice_number, work_order, collection_reason, product_name):
    return switched(
        "تفاصيل الطلب",
        (invoice_number, f("invoice_number", "رقم الفاتورة المطلوب السداد عليها، إن توفر")),
        (work_order, f("work_order", "رقم أمر الشغل، إن توفر")),
        (collection_reason, f("collection_reason", "سبب التحصيل", "select",
                              options=["باقي فاتورة", "أعمال إضافية", "أخرى"])),
        (product_name, f("product_name", "المنتج / الخدمة المرتبط بها التحصيل", "product")),
    )


def amounts(*, paid_amount, amount_distribution):
    return switched(
        "قيمة الطلب",
        (paid_amount, money("paid_amount", "المبلغ المحصل نقدًا الآن", positive=True)),
        (amount_distribution, f("amount_distribution",
                                "توزيع المبلغ على الفواتير / الأسباب، إن شمل أكثر من فاتورة أو سبب", "textarea")),
    )


def payment(*, payment_method, payment_date, paper_receipt_number, technician_name):
    """تفاصيل الدفعة: always cash, collected by a technician against a paper receipt."""
    return switched(
        "تفاصيل الدفعة",
        (payment_method, f("payment_method", "طريقة الدفع", "select", options=[CASH], default=CASH)),
        (payment_date, f("payment_date", "تاريخ الدفع", "date", default="today", not_future=True)),
        (paper_receipt_number, f("paper_receipt_number", "رقم سند القبض الورقي")),
        (technician_name, f("technician_name", "اسم الفني المحصل", "staff")),
    )


def attachments(*, receipt_image, invoice_image):
    return switched(
        "المرفقات",
        (receipt_image, files("receipt_image", "صورة سند القبض الورقي")),
        (invoice_image, files("invoice_image", "صورة الفاتورة المرتبطة، إن توفرت")),
    )


SECTIONS = [
    shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=HIDE, source=REQUIRED,
                        labels={"request_date": "تاريخ الطلب"}),
    shared.client(
        phone=REQUIRED, phone2=SHOW, client_code=REQUIRED, customer_name=REQUIRED, customer_type=SHOW, gender=SHOW,
        email=HIDE, labels={"customer_name": "اسم العميل"},
    ),
    order_details(invoice_number=SHOW, work_order=SHOW, collection_reason=REQUIRED, product_name=REQUIRED),
    amounts(paid_amount=REQUIRED, amount_distribution=SHOW),
    payment(payment_method=REQUIRED, payment_date=REQUIRED, paper_receipt_number=REQUIRED, technician_name=REQUIRED),
    attachments(receipt_image=REQUIRED, invoice_image=SHOW),
    shared.notes(notes=SHOW),
]
