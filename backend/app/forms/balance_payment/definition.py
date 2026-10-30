"""The fields of طلب تسديد مبلغ متبقي, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    NOTES,
    PAYMENT_METHODS,
    TREASURY_BY_METHOD,
    attachments,
    f,
    files,
    money,
    request_info,
    section,
)

SECTIONS = [
    request_info("تاريخ الطلب", source=False),
    section(
        "بيانات العميل",
        f("phone", "رقم الهاتف", "phone", True),
        f("client_code", "كود العميل", required=True, pattern=r"^\d{1,6}$", pattern_message="أرقام فقط، حتى 6 خانات"),
        f("customer_name", "اسم العميل", required=True, max_length=150),
        f("invoice", "رقم الفاتورة", "daftra_client_invoice", True),
        note="بعد العثور على العميل تظهر فواتيره التي عليها مبلغ متبقٍ، الأحدث أولًا.",
    ),
    section("قيمة الطلب", money("paid_amount", "المبلغ المدفوع الآن", True, positive=True)),
    section(
        "تفاصيل الدفعة",
        f("payment_method", "طريقة الدفع", "select", True, options=PAYMENT_METHODS),
        f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury", True,
          default_from={"field": "payment_method", "values": TREASURY_BY_METHOD}),
        f("collector_name", "اسم المحصل", "staff", True),
        f("payment_date", "تاريخ التحصيل", "date", True, default="today", not_future=True),
        f("payment_reference", "رقم التحويل / السند الورقي", required=True),
    ),
    attachments(files("payment_proof", "صورة التحويل / الإيصال", True)),
    NOTES,
]
