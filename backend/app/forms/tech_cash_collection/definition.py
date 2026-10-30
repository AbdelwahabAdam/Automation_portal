"""The fields of تسجيل تحصيل نقدي بواسطة الفني, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import CASH, NOTES, attachments, client, f, files, money, request_info, section

SECTIONS = [
    request_info("تاريخ الطلب"),
    client(True, "اسم العميل"),
    section(
        "تفاصيل الطلب",
        f("invoice_number", "رقم الفاتورة المطلوب السداد عليها، إن توفر"),
        f("work_order", "رقم أمر الشغل، إن توفر"),
        f("collection_reason", "سبب التحصيل", "select", True, options=["باقي فاتورة", "أعمال إضافية", "أخرى"]),
        f("product_name", "المنتج / الخدمة المرتبط بها التحصيل", "product", True),
    ),
    section(
        "قيمة الطلب",
        money("paid_amount", "المبلغ المحصل نقدًا الآن", True, positive=True),
        f("amount_distribution", "توزيع المبلغ على الفواتير / الأسباب، إن شمل أكثر من فاتورة أو سبب", "textarea"),
    ),
    section(
        "تفاصيل الدفعة",
        f("payment_method", "طريقة الدفع", "select", True, options=[CASH], default=CASH),
        f("payment_date", "تاريخ الدفع", "date", True, default="today", not_future=True),
        f("paper_receipt_number", "رقم سند القبض الورقي", required=True),
        f("technician_name", "اسم الفني المحصل", "staff", required=True),
    ),
    attachments(
        files("receipt_image", "صورة سند القبض الورقي", True),
        files("invoice_image", "صورة الفاتورة المرتبطة، إن توفرت"),
    ),
    NOTES,
]
