"""What طلب تسديد مبلغ متبقي asks: its sections, with one switch per field, and the one check the
field rules cannot express.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import HIDE, PAYMENT_METHODS, REQUIRED, SHOW, f, files, money, shared, switched, \
    switched_fields

# Daftra rounds each line's tax on its own, so an amount may be a hair over the unpaid total
PAID_TOLERANCE = 0.005


def validate(data: dict, ctx) -> dict:
    """What is paid now cannot be more than the chosen invoice still has to pay."""
    invoices = ctx.choices.get("daftra_client_invoice") or []
    chosen = next((invoice for invoice in invoices if invoice["id"] == data.get("invoice")), None)
    if chosen and data.get("paid_amount", 0) > chosen["unpaid"] + PAID_TOLERANCE:
        return {"paid_amount": f"المبلغ أكبر من المتبقي على الفاتورة ({chosen['unpaid']:,.2f} درهم)"}
    return {}


# ---------- this form's own sections ----------

def client(*, invoice, **switches):
    """بيانات العميل, then the invoice being paid: the client's open invoices, newest first."""
    section = shared.client(**switches, labels={"customer_name": "اسم العميل"},
                            note="بعد العثور على العميل تظهر فواتيره التي عليها مبلغ متبقٍ، الأحدث أولًا.")
    section["fields"] += switched_fields((invoice, f("invoice", "رقم الفاتورة", "daftra_client_invoice")))
    return section


def amounts(*, paid_amount):
    return switched("قيمة الطلب", (paid_amount, money("paid_amount", "المبلغ المدفوع الآن", positive=True)))


def payment(*, payment_method, treasury, collector_name, payment_date, payment_reference):
    """تفاصيل الدفعة: who collected it before when, unlike the shared section."""
    return switched(
        "تفاصيل الدفعة",
        (payment_method, f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS)),
        (treasury, f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury")),
        (collector_name, f("collector_name", "اسم المحصل", "staff")),
        (payment_date, f("payment_date", "تاريخ التحصيل", "date", default="today", not_future=True)),
        (payment_reference, f("payment_reference", "رقم التحويل / السند الورقي")),
    )


def attachments(*, payment_proof):
    return switched("المرفقات", (payment_proof, files("payment_proof", "صورة التحويل / الإيصال")))


# ---------- the form ----------

SECTIONS = [
    shared.request_info(
        request_date=REQUIRED,
        employee_name=SHOW,
        order_source=HIDE,                   # the invoice being paid already has one
        source=HIDE,
        labels={"request_date": "تاريخ الطلب"},
    ),
    client(
        phone=REQUIRED,
        phone2=HIDE,
        client_code=REQUIRED,
        customer_name=REQUIRED,
        customer_type=SHOW,
        gender=SHOW,
        email=HIDE,
        invoice=REQUIRED,
    ),
    amounts(paid_amount=REQUIRED),
    payment(
        payment_method=REQUIRED,
        treasury=REQUIRED,
        collector_name=REQUIRED,
        payment_date=REQUIRED,
        payment_reference=REQUIRED,
    ),
    attachments(payment_proof=REQUIRED),
    shared.notes(notes=SHOW),
]
