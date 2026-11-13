"""The sections many forms share, each taking one switch per field (see `switches.py`).

A form names every field of a section it uses — the arguments are keyword-only and none has a
default — so a form that forgets one, or misspells one, fails when the app starts rather than
when someone opens it:

    shared.client(phone=REQUIRED, phone2=SHOW, client_code=SHOW, customer_name=REQUIRED,
                  customer_type=SHOW, gender=SHOW, email=NEW_CLIENT(SHOW))

`labels=` changes what a field is called on this form: {"request_date": "تاريخ الطلب"}.
`placeholders=` what it says while it is empty: {"email": "تُرسل إليه الفاتورة"}.

What a field *is* stays here: its type, its pattern, what computes it. Two labels follow the
switch rather than the form, because they say whether the field must be filled:
«كود العميل» / «كود العميل، إن وجد», and the due date of what is left (an instalment in Daftra
when it is demanded, a date «إن وجد» when it is not).
"""

from .fields import f, money
from .options import DISCOUNT_AMOUNTS, DISCOUNT_LABELS, DISCOUNTED, EMIRATES, PAYMENT_METHODS, SOURCES
from .options import CUSTOMER_TYPES, GENDERS
from .switches import Switch, apply, check, shown

#: What makes the due date of the remainder demanded: something is left to pay
HAS_REMAINDER = {"field": "remaining_amount", "gt": 0}


def _labelled(labels: dict | None, known: set[str]) -> dict:
    """The form's own labels, refusing one for a field the section does not have."""
    labels = labels or {}
    unknown = set(labels) - known
    if unknown:
        raise TypeError(f"labels= names fields this section has not got: {', '.join(sorted(unknown))}")
    return labels


def _build(title: str, note: str | None, pairs: list[tuple[str, Switch, dict]],
           placeholders: dict | None = None) -> dict:
    placeholders = _labelled(placeholders, {name for name, _, _ in pairs})
    fields = []
    for name, switch, field in pairs:
        if name in placeholders:
            field = {**field, "placeholder": placeholders[name]}
        made = apply(check(name, switch), field)
        if made is not None:
            fields.append(made)
    return {"title": title, "note": note, "fields": fields}


# ---------- بيانات الطلب ----------

def request_info(*, request_date: Switch, employee_name: Switch, order_source: Switch, source: Switch,
                 labels: dict | None = None, note: str | None = None) -> dict:
    """بيانات الطلب.

    order_source: Daftra's own list, for a form whose approval creates an invoice.
    source: the portal's list, for one that creates nothing. A form shows one or neither.
    """
    labels = _labelled(labels, {"request_date", "employee_name", "order_source", "source"})
    if shown(order_source) and shown(source):
        raise TypeError("request_info shows order_source or source, not both: they are the same question")
    return _build("بيانات الطلب", note, [
        ("request_date", request_date,
         f("request_date", labels.get("request_date", "تاريخ الاتفاق مع العميل"), "date",
           default="today", not_future=True)),
        ("employee_name", employee_name,
         f("employee_name", labels.get("employee_name", "اسم الموظف"), "auto_user")),
        ("order_source", order_source,
         f("order_source", labels.get("order_source", "مصدر الطلب في دفترة"), "daftra_order_source")),
        ("source", source,
         f("source", labels.get("source", "مصدر الطلب"), "select", options=SOURCES)),
    ])


# ---------- بيانات العميل ----------

def client(*, phone: Switch, phone2: Switch, client_code: Switch, customer_name: Switch,
           customer_type: Switch, gender: Switch, email: Switch,
           labels: dict | None = None, placeholders: dict | None = None, note: str | None = None) -> dict:
    """بيانات العميل.

    email=NEW_CLIENT(SHOW): asked only while the phone search finds nobody, because Daftra keeps
    it on a client it creates and already has it for one it knows.
    """
    labels = _labelled(labels, {"phone", "phone2", "client_code", "customer_name", "customer_type",
                                "gender", "email"})
    code_label = "كود العميل" if check("client_code", client_code).kind == "required" else "كود العميل، إن وجد"
    return _build("بيانات العميل", note, [
        ("phone", phone, f("phone", labels.get("phone", "رقم الهاتف"), "phone")),
        # Daftra keeps two numbers per client, and half of them have a second. It is the number of
        # someone else to reach there, so the work order names it so too.
        ("phone2", phone2, f("phone2", labels.get("phone2", "رقم مسؤول اخر"), "phone")),
        ("client_code", client_code,
         f("client_code", labels.get("client_code", code_label),
           pattern=r"^\d{1,6}$", pattern_message="أرقام فقط، حتى 6 خانات")),
        ("customer_name", customer_name,
         f("customer_name", labels.get("customer_name", "اسم العميل المطلوب على الفاتورة"), max_length=150)),
        # They reach Daftra only when approving creates a new client; one Daftra already has keeps
        # what it holds, and they stay on the request
        ("customer_type", customer_type,
         f("customer_type", labels.get("customer_type", "نوع العميل"), "select",
           options=list(CUSTOMER_TYPES), dropdown=True)),
        ("gender", gender,
         f("gender", labels.get("gender", "الجنس"), "select", options=list(GENDERS), dropdown=True)),
        ("email", email, f("email", labels.get("email", "البريد الإلكتروني، إن وجد"), "email")),
    ], placeholders)


# ---------- عنوان الخدمة ----------

def address(*, category: Switch, area: Switch, emirate: Switch, street: Switch, house: Switch,
            location_url: Switch, coordinates: Switch,
            title: str = "عنوان الخدمة", labels: dict | None = None, note: str | None = None) -> dict:
    """عنوان الخدمة. التصنيف, المنطقة and الإمارة follow and narrow each other as the form is filled
    in (frontend modules/requests/address.js); المنطقة is never typed — it is the التصنيف itself."""
    labels = _labelled(labels, {"category", "area", "emirate", "street", "house", "location_url", "coordinates"})
    return _build(title, note, [
        ("category", category,
         f("category", labels.get("category", "التصنيف"), "daftra_client_category")),
        ("area", area,
         f("area", labels.get("area", "المنطقة"), "text", max_length=100, readonly=True, from_category="category")),
        ("emirate", emirate,
         f("emirate", labels.get("emirate", "الإمارة"), "select", options=EMIRATES)),
        ("street", street, f("street", labels.get("street", "الشارع"))),
        ("house", house, f("house", labels.get("house", "رقم البيت / اسم الموقع"))),
        # As خرائط جوجل shares it. 255 is as long as Daftra's own field.
        ("location_url", location_url,
         f("location_url", labels.get("location_url", "موقع العميل"), "text", max_length=255,
           pattern=r"^https?://\S+$", pattern_message="الصق رابط الموقع من خرائط جوجل",
           placeholder="https://maps.app.goo.gl/…")),
        # Daftra demands them on every client; a link carrying a point fills them in
        ("coordinates", coordinates,
         f("coordinates", labels.get("coordinates", "الإحداثيات"), max_length=100, ltr=True,
           coordinates_from="location_url", placeholder="مثال: 24.178700, 55.604510")),
    ])


# ---------- قيمة الطلب ----------

def amounts(*, subtotal_amount: Switch, total_amount: Switch, discount_label: Switch,
            discount_amount: Switch, discount_approved_by: Switch, paid_amount: Switch,
            remaining_amount: Switch, remaining_due_date: Switch,
            must_pay: bool = False, price_default: int | None = None, paid_default: str | None = None,
            labels: dict | None = None, note: str | None = None) -> dict:
    """قيمة الطلب.

    An amount the form works out is SHOW; one the salesperson types is REQUIRED:

        subtotal_amount  SHOW: the order lines' total.  REQUIRED: typed, starting at price_default.
        total_amount     SHOW: the subtotal less the discount, or the lines' total with no subtotal.
                         REQUIRED: typed.
        remaining_amount SHOW: the total less what is paid.

    discount_label shown: the discount is printed on the Daftra invoice under a name, and then
    «المبلغ المدفوع» sits between the discount and who approved it, as the invoiced forms have it.
    remaining_due_date REQUIRED_IF(HAS_REMAINDER): the remainder is an instalment in Daftra.
    must_pay: what is paid now must be more than 0.
    """
    labels = _labelled(labels, {"subtotal_amount", "total_amount", "discount_label", "discount_amount",
                                "discount_approved_by", "paid_amount", "remaining_amount", "remaining_due_date"})
    switches = {name: check(name, value) for name, value in {
        "subtotal_amount": subtotal_amount, "total_amount": total_amount, "discount_label": discount_label,
        "discount_amount": discount_amount, "discount_approved_by": discount_approved_by,
        "paid_amount": paid_amount, "remaining_amount": remaining_amount,
        "remaining_due_date": remaining_due_date}.items()}
    _check_amounts(switches)

    subtotal_typed = switches["subtotal_amount"].kind == "required"
    subtotal_label = labels.get("subtotal_amount", "قيمة الطلب النهائية قبل الخصم، شامل الضريبة والإضافات")
    subtotal = (money("subtotal_amount", subtotal_label, positive=True,
                      **({"default": str(price_default)} if price_default else {}))
                if subtotal_typed else
                f("subtotal_amount", subtotal_label, "number", money=True, computed=[]))

    total_label = labels.get("total_amount", "قيمة الطلب النهائية بعد الخصم، شامل الضريبة والإضافات")
    if switches["total_amount"].kind == "required":
        total = money("total_amount", total_label)
    elif shown(switches["subtotal_amount"]):
        total = f("total_amount", total_label, "number", money=True,
                  computed=["subtotal_amount", "discount_amount"],
                  negative_message="قيمة الخصم أكبر من قيمة الطلب قبل الخصم")
    else:
        # The order lines fill it in (their subtotal_field names it): nothing is taken off
        total = f("total_amount", total_label, "number", money=True, computed=[])

    paid = money("paid_amount", labels.get("paid_amount", "المبلغ المدفوع فعليًا الآن"), positive=must_pay,
                 **({"default": paid_default} if paid_default is not None else {}))
    named = f("discount_label", labels.get("discount_label", "اسم الخصم كما يظهر في الفاتورة"),
              max_length=100, suggestions=DISCOUNT_LABELS, fills="discount_amount",
              fills_by_choice=DISCOUNT_AMOUNTS)
    amount = money("discount_amount", labels.get("discount_amount", "قيمة الخصم، إن وجد"))
    approved = f("discount_approved_by", labels.get("discount_approved_by", "اسم الشخص الذي اعتمد الخصم"), "staff")
    # A named discount's name comes first: picking an initiative fills قيمة الخصم, beside it
    middle = ([("discount_label", named), ("discount_amount", amount), ("paid_amount", paid),
               ("discount_approved_by", approved)]
              if shown(switches["discount_label"]) else
              [("discount_amount", amount), ("discount_approved_by", approved), ("paid_amount", paid)])

    instalment = switches["remaining_due_date"].kind == "required_if"
    due = f("remaining_due_date", labels.get(
        "remaining_due_date", "موعد سداد المتبقي (قسط اتفاقية التقسيط)" if instalment else "موعد سداد المتبقي، إن وجد"),
        "date")
    remaining = f("remaining_amount", labels.get("remaining_amount", "المبلغ المتبقي"), "number", money=True,
                  computed=["total_amount", "paid_amount"], negative_message="المبلغ المدفوع أكبر من قيمة الطلب")

    order = [("subtotal_amount", subtotal), ("total_amount", total), *middle,
             ("remaining_amount", remaining), ("remaining_due_date", due)]
    return _build("قيمة الطلب", note, [(name, switches[name], field) for name, field in order])


def _check_amounts(s: dict[str, Switch]):
    """The combinations an amount cannot be worked out from are refused when the form loads."""
    def kind(name):
        return s[name].kind

    if not shown(s["total_amount"]):
        raise TypeError("amounts: total_amount cannot be hidden — every other amount is worked out from it")
    if kind("subtotal_amount") not in ("hide", "show", "required"):
        raise TypeError("amounts: subtotal_amount is SHOW (from the order lines) or REQUIRED (typed)")
    if kind("total_amount") not in ("show", "required"):
        raise TypeError("amounts: total_amount is SHOW (worked out) or REQUIRED (typed)")
    if shown(s["subtotal_amount"]) and kind("total_amount") != "show":
        raise TypeError("amounts: with a subtotal, the total is worked out from it — total_amount=SHOW")
    if kind("remaining_amount") not in ("hide", "show"):
        raise TypeError("amounts: remaining_amount is worked out — SHOW or HIDE")
    if shown(s["remaining_amount"]) and not shown(s["paid_amount"]):
        raise TypeError("amounts: remaining_amount is the total less paid_amount, which is hidden")
    if shown(s["remaining_due_date"]) and not shown(s["remaining_amount"]):
        raise TypeError("amounts: remaining_due_date is when remaining_amount falls due, which is hidden")
    discount = [name for name in ("discount_label", "discount_approved_by") if shown(s[name])]
    if discount and not shown(s["discount_amount"]):
        raise TypeError(f"amounts: {', '.join(discount)} describe a discount, but discount_amount is hidden")


# ---------- تفاصيل الدفعة ----------

def payment(*, payment_method: Switch, treasury: Switch, payment_date: Switch, payment_reference: Switch,
            collector_name: Switch, title: str = "تفاصيل الدفعة",
            labels: dict | None = None, note: str | None = None) -> dict:
    """تفاصيل الدفعة. treasury: the Daftra account a receipt is paid into, for a form whose
    approval makes one — chosen by hand, as طريقة الدفع does not say which account it went to."""
    labels = _labelled(labels, {"payment_method", "treasury", "payment_date", "payment_reference",
                                "collector_name"})
    return _build(title, note, [
        ("payment_method", payment_method,
         f("payment_method", labels.get("payment_method", "طريقة الدفع"), "select", options=PAYMENT_METHODS)),
        ("treasury", treasury,
         f("treasury", labels.get("treasury", "الخزينة / الحساب المستلم في دفترة"), "daftra_treasury")),
        # Today, because a payment is nearly always taken on the day the request is written
        ("payment_date", payment_date,
         f("payment_date", labels.get("payment_date", "تاريخ الدفع"), "date", default="today", not_future=True)),
        ("payment_reference", payment_reference,
         f("payment_reference", labels.get("payment_reference", "رقم التحويل / طلب تابي / السند الورقي"))),
        ("collector_name", collector_name,
         f("collector_name", labels.get("collector_name", "اسم المحصل، في حالة الدفع النقدي"), "staff")),
    ])


# ---------- ملاحظات ----------

def notes(*, notes: Switch, labels: dict | None = None) -> dict:
    labels = _labelled(labels, {"notes"})
    return _build("ملاحظات", None, [
        ("notes", notes, f("notes", labels.get("notes", "أي اتفاق خاص أو ملاحظات إضافية"), "textarea")),
    ])


__all__ = ["DISCOUNTED", "HAS_REMAINDER", "address", "amounts", "client", "notes", "payment", "request_info"]
