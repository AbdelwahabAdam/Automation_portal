"""Building blocks the form definitions are written with: one field, and the sections several forms share."""

from .options import (AREAS, AREAS_BY_EMIRATE, CASH_PAYMENT, DISCOUNT_LABELS, DISCOUNTED, EMIRATES, NO_INSCRIPTION,
    PAYMENT_METHODS, SOURCES, TREASURY_BY_METHOD, YES_NO)


def f(name, label, type="text", required=False, **extra):
    return {"name": name, "label": label, "type": type, "required": required, **extra}


def money(name, label, required=False, **extra):
    # money=True: an amount in dirhams, which the form and the request's page print with its unit
    return f(name, label, "number", required, min=0, money=True, **extra)


def yes_no(name, label, required=True, **extra):
    return f(name, label, "select", required, options=YES_NO, **extra)


def files(name, label, required=False, **extra):
    return f(name, label, "files", required, **extra)


def section(title, *fields, note=None):
    return {"title": title, "note": note, "fields": list(fields)}


def need(condition):
    """required=True, or required only when the condition holds."""
    return {"required": True} if condition is True else {"required_if": condition}


def request_info(date_label="تاريخ الاتفاق مع العميل", invoiced=False, source=True):
    # invoiced: approving the request creates a Daftra invoice, so the order source is Daftra's own list
    # source=False: no order source at all (e.g. a payment on an invoice that already has one)
    source_field = (f("order_source", "مصدر الطلب في دفترة", "daftra_order_source", True) if invoiced
                    else f("source", "مصدر الطلب", "select", True, options=SOURCES))
    return section(
        "بيانات الطلب",
        f("request_date", date_label, "date", True, default="today", not_future=True),
        f("employee_name", "اسم الموظف", "auto_user"),
        *([source_field] if source else []),
    )


def client(code_required, name_label="اسم العميل المطلوب على الفاتورة"):
    return section(
        "بيانات العميل",
        f("phone", "رقم الهاتف", "phone", True),
        f("client_code", "كود العميل" if code_required else "كود العميل، إن وجد", required=code_required,
          pattern=r"^\d{1,6}$", pattern_message="أرقام فقط، حتى 6 خانات"),
        f("customer_name", name_label, required=True, max_length=150),
    )


def address(title="عنوان الخدمة", required=True):
    # Every form asks for the same address as طلب بيع لعميل جديد, where the coordinates are the
    # Coordinates a client created in Daftra needs; they fill in from a location link that has them.
    # التصنيف is the client's category in Daftra (set on the client when a Daftra form is approved);
    # picking it fills in المنطقة and الإمارة, and picking the area fills in its emirate (RequestForm.jsx)
    return section(
        title,
        f("category", "التصنيف", "daftra_client_category", required),
        # Not a list to pick from: Daftra holds a neighbourhood here («الخوانيج 2»), which is what
        # the installation team needs on the work order, and only 28 of our 3,931 client addresses
        # hold one of the regions below. They are offered as suggestions instead.
        f("area", "المنطقة", "text", required, max_length=100, suggestions=AREAS,
          areas_by_emirate=AREAS_BY_EMIRATE),
        f("emirate", "الإمارة", "select", required, options=EMIRATES),
        f("street", "الشارع"),
        f("house", "رقم البيت / اسم الموقع"),
        f("location_url", "رابط اللوكيشن", max_length=600),
        f("coordinates", "الإحداثيات (مثل 24.1787, 55.6045)" if required else "الإحداثيات، إن توفرت (مثل 24.1787, 55.6045)",
          required=required, max_length=100, coordinates_from="location_url"),
    )


def original_refs():
    return [
        f("original_order", "رقم الطلب الأصلي، إن توفر"),
        f("original_invoice", "رقم الفاتورة الأصلية، إن توفر"),
        f("work_order", "رقم أمر الشغل، إن توفر"),
    ]


def discount_fields(label="قيمة الخصم، إن وجد"):
    return [
        money("discount_amount", label),
        f("discount_approved_by", "اسم الشخص الذي اعتمد الخصم", "staff", required_if=DISCOUNTED),
    ]


def amounts(total_label="قيمة الطلب النهائية بعد الخصم، شامل الضريبة والإضافات",
            discount_label="قيمة الخصم، إن وجد", paid_label="المبلغ المدفوع فعليًا الآن",
            remaining_label="المبلغ المتبقي", must_pay=False, auto_total=False, invoiced=False,
            price_label=None, price_default=None):
    # auto_total: the order lines' catalog prices work out the total, instead of the salesperson typing it
    # price_label: the salesperson types the price before discount (starting at price_default) and the total follows
    # invoiced: the discount is printed on the Daftra invoice under a name, e.g. «مبادرة دعم نبع المزن»
    computed_total = auto_total or price_label
    total_field = (
        f("total_amount", total_label, "number", money=True, computed=["subtotal_amount", "discount_amount"],
          negative_message="قيمة الخصم أكبر من قيمة الطلب قبل الخصم")
        if computed_total else money("total_amount", total_label, True)
    )
    if auto_total:
        subtotal = [f("subtotal_amount", "قيمة الطلب النهائية قبل الخصم، شامل الضريبة والإضافات", "number",
                      money=True, computed=[])]
    elif price_label:
        subtotal = [money("subtotal_amount", price_label, True, positive=True,
                          **({"default": str(price_default)} if price_default else {}))]
    else:
        subtotal = []
    return section(
        "قيمة الطلب",
        *subtotal,
        total_field,
        *discount_fields(discount_label),
        # Before the discount's name, so the two share a line with the amount paid on the right
        money("paid_amount", paid_label, True, positive=must_pay),
        *([f("discount_label", "اسم الخصم كما يظهر في الفاتورة", required_if=DISCOUNTED, max_length=100,
             suggestions=DISCOUNT_LABELS)] if invoiced else []),
        f("remaining_amount", remaining_label, "number", money=True, computed=["total_amount", "paid_amount"],
          negative_message="المبلغ المدفوع أكبر من قيمة الطلب"),
        # invoiced: what is left becomes a one-installment agreement in Daftra, due on this date
        f("remaining_due_date", "موعد سداد المتبقي (قسط اتفاقية التقسيط)", "date",
          required_if={"field": "remaining_amount", "gt": 0})
        if invoiced else f("remaining_due_date", "موعد سداد المتبقي، إن وجد", "date"),
    )


def payment(title="تفاصيل الدفعة", when=True, invoiced=False):
    # invoiced: the payment becomes a Daftra receipt, which needs the treasury it was received into
    return section(
        title,
        f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, **need(when)),
        *([f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury",
             default_from={"field": "payment_method", "values": TREASURY_BY_METHOD}, **need(when))] if invoiced else []),
        f("payment_date", "تاريخ الدفع", "date", not_future=True, **need(when)),
        f("payment_reference", "رقم التحويل / طلب تابي / السند الورقي", **need(when)),
        f("collector_name", "اسم المحصل، في حالة الدفع النقدي", "staff", required_if=CASH_PAYMENT),
    )


def attachments(*fields):
    return section("المرفقات", *fields)


NOTES = section("ملاحظات", f("notes", "أي اتفاق خاص أو ملاحظات إضافية", "textarea"))
INSCRIPTION = [
    # blank_value: left empty it saves as «لا يوجد», so there is no inscription to write or charge for
    f("inscription", "الكتابة المطلوبة (النص حرفيًا، واتركه فارغًا إن لم تكن مطلوبة)", "textarea",
      blank_value=NO_INSCRIPTION[0]),
    f("inscription_place", "مكان الكتابة، إن وجدت"),
]
