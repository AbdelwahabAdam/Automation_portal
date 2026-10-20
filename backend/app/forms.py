"""Form definitions and their validation.

The frontend renders forms from these definitions and the backend validates
submissions against the same definitions, so a form is described in one place.
The forms follow the sales templates in forms.md.
"""

import re
from datetime import date

YES_NO = ["نعم", "لا"]
CASH = "نقدًا"
EMIRATES = ["أبوظبي", "دبي", "الشارقة", "عجمان", "أم القيوين", "رأس الخيمة", "الفجيرة"]
# Each emirate's areas, from UAE_Location_Reference.xlsx's Areas sheet (active rows only);
# no area name repeats across emirates, so a picked area also picks its emirate.
AREAS_BY_EMIRATE = {
    "أبوظبي": ["منطقة أبوظبي", "منطقة العين", "منطقة الظفرة"],
    "دبي": ["مدينة دبي", "حتا"],
    "الشارقة": ["مدينة الشارقة", "الحمرية", "الذيد", "البطائح", "مليحة", "المدام", "خورفكان", "كلباء", "دبا الحصن"],
    "عجمان": ["مدينة عجمان", "المنامة", "مصفوت"],
    "أم القيوين": ["مدينة أم القيوين", "فلج المعلا", "الحمرة", "الرملة"],
    "رأس الخيمة": ["نطاق مدينة رأس الخيمة", "المنطقة الشمالية", "المنطقة الجنوبية", "منطقة النخيل", "نطاق الظيت الجنوبي–خت"],
    "الفجيرة": ["مدينة الفجيرة", "دبا الفجيرة"],
}
AREAS = [area for areas in AREAS_BY_EMIRATE.values() for area in areas]
PAYMENT_METHODS = ["تحويل بنكي", CASH, "ماكينة POS", "تابي", "تمارا", "طلب من الموقع"]
REFUND_METHODS = ["تحويل بنكي", CASH, "تابي", "تمارا", "أخرى"]
SOURCES = ["ماركتنج", "عميل شركة", "عميل جديد", "عميل سابق", "مكتب", "الموقع", "أخرى"]
WORK_STATUS = ["مطلوب تنفيذها", "تم تنفيذها", "تم تنفيذ جزء منها"]
WORK_STARTED = WORK_STATUS[1:]
COLORS = ["أبيض", "أسود", "ذهبي", "أخرى"]

PHONE_RE = re.compile(r"^(?:\+?971|0)\d{8,9}$")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Field type "product" holds a name picked from our catalog, "staff" one picked from Daftra's staff list
DEFAULT_MAX_LENGTH = {"text": 300, "product": 300, "staff": 300, "textarea": 3000, "package_color": 300}
# Field types holding the id of a row in a Daftra list; the form shows the list, the data keeps the
# id in the field and the row's name in "<field>_name"
DAFTRA_LIST_TYPES = ("daftra_order_source", "daftra_treasury", "daftra_client_category", "daftra_client_invoice")
# The renewal price a طلب تجديد عقد الصيانة السنوي starts from; the salesperson can change it
RENEWAL_PRICE = 1680
# What an inscription field holds when there is no inscription, so nothing is charged for it
NO_INSCRIPTION = ["لا يوجد", "لايوجد", "لا توجد", "لاتوجد"]
# Names already used for discounts on our Daftra invoices, offered as suggestions
DISCOUNT_LABELS = ["مبادرة دعم نبع المزن", "مبادرة دعم سقيا الخير", "مبادرة لك ان تشارك", "خصم من قبل الإدارة"]
# The treasury a payment usually goes into in Daftra, by payment method; the salesperson can change it
TREASURY_BY_METHOD = dict(zip(PAYMENT_METHODS, [13, 9, 16, 7, 8, 12]))

# Conditions used with required_if
PAID = {"field": "paid_amount", "gt": 0}
DISCOUNTED = {"field": "discount_amount", "gt": 0}
CASH_PAYMENT = {"field": "payment_method", "equals": CASH}
HAS_INSCRIPTION = {"field": "inscription", "not_in": NO_INSCRIPTION}
WANTS_WORK_ORDER = {"field": "create_work_order", "equals": "نعم"}
# A package's cover colours (لون الغطاء) depend on the package. Each family: the words its package names
# contain (and must not contain), and its colours as (shown in the form, written on the Daftra work order
# as «الألوان المتاحة», exactly as staff write it there). The first family that matches wins; a package
# that matches none has no colours to pick.
PACKAGE_COLOR_FAMILIES = [
    {"match": ["سقيا الخير مدمجة"], "exclude": [], "colors": [
        ("الابيض", "سقيا الخير مدمجه - اللون الابيض"),
        ("الاسود", "سقيا الخير مدمجه - اللون الاسود"),
        ("الابيض * الابيض", "سقيا الخير مدمجه - اللون الابيض * الابيض"),
        ("الابيض * الذهبى", "سقيا الخير مدمجه - اللون الابيض * الذهبى"),
    ]},
    {"match": ["سقيا الخير"], "exclude": ["ستانلس", "حفظ الطعام"], "colors": [
        ("الابيض * خشابي مقاس طبيعي", "سقيا الخير  - اللون الابيض * خشابي مقاس طبيعي"),
        ("الاسود مقاس طبيعي", "سقيا الخير-  اللون الاسود مقاس طبيعي"),
        ("الابيض * ابيض مقاس طبيعي", "سقيا الخير - اللون الابيض * ابيض مقاس طبيعي"),
        ("الابيض * ذهبي مقاس طبيعي", "سقيا الخير - اللون الابيض * ذهبي مقاس طبيعي"),
        ("الاسود * الخشبي مقاس طبيعي", "سقيا الخير - اللون الاسود * الخشبي مقاس طبيعي"),
        ("الاسود * الاسود مقاس طبيعي", "سقيا الخير - اللون الاسود * الاسود مقاس طبيعي"),
    ]},
    {"match": ["نبع المزن"], "exclude": ["حفظ الطعام"], "colors": [
        ("البني والأسود", "نبع المزن – اللون البني والأسود"),
        ("الأبيض والذهبي المطفي", "نبع المزن – اللون الأبيض والذهبي المطفي"),
        ("الرصاصي والأبيض", "نبع المزن – اللون الرصاصي والأبيض"),
        ("البني والأبيض", "نبع المزن – اللون البني والأبيض"),
        ("الرصاصي والأسود", "نبع المزن – اللون الرصاصي والأسود"),
        ("الأبيض والذهبي لامع", "نبع المزن – اللون الأبيض والذهبي لامع"),
        ("الأبيض والعيناوي", "نبع المزن – اللون الأبيض والعيناوي"),
        ("الأبيض * الابيض", "نبع المزن – اللون الأبيض * الابيض"),
        ("الرصاصي* الذهبي مط", "نبع المزن – اللون الرصاصي* الذهبي مط"),
        ("البني * الذهبي مط", "نبع المزن – اللون البني * الذهبي مط"),
        ("الأبيض *  اللون الاسود", "نبع المزن – اللون الأبيض *  اللون الاسود"),
        ("الرصاصي* الخشبي", "نبع المزن – اللون الرصاصي* الخشبي"),
    ]},
    {"match": ["6 صنابير"], "exclude": [], "colors": [("6 ولف ابيض", "براد سبيل - 6 ولف ابيض")]},
]


def package_colors(package_name: str) -> list[tuple[str, str]]:
    """The colours a package's name allows, as (shown, as written on the work order); [] for none.
    frontend/src/validation.js packageColors() mirrors this."""
    name = " ".join(str(package_name or "").split())
    for family in PACKAGE_COLOR_FAMILIES:
        if any(word in name for word in family["match"]) and not any(word in name for word in family["exclude"]):
            return family["colors"]
    return []


MAX_PACKAGE_QUANTITY = 99

# The devices a maintenance visit can be for (several may be picked)
MAINTENANCE_DEVICES = [
    "برادة نبع المزن — 2 حنفية", "برادة نبع المزن — 3 حنفيات", "برادة نبع المزن — 4 حنفيات",
    "برادة نبع المزن المدمجة — برادة مياه + ثلاجة طعام", "برادة نبع المزن جامبو — بدون ثلاجة طعام",
    "برادة حفظ النعمة — بغطاء نبع المزن",
    "برادة سقيا الخير — 2 حنفية", "برادة سقيا الخير — 3 حنفيات", "برادة سقيا الخير — 4 حنفيات",
    "برادة سقيا الخير المدمجة — برادة مياه + ثلاجة طعام", "برادة سقيا الخير المدمجة سبيشال — برادتا مياه + ثلاجة طعام",
    "برادة حفظ النعمة — بغطاء سقيا الخير",
    "برادة سقيا الخير ستانلس — 2 حنفية", "برادة سقيا الخير ستانلس — 3 حنفيات", "برادة سقيا الخير ستانلس — 4 حنفيات",
    "برادة مياه — 6 حنفيات", "موزع مياه مع RO — 3 حنفيات",
    "فلتر R3 — ثلاث مراحل", "فلتر جامبو ثنائي — J2", "فلتر جامبو ثلاثي — J3",
    "فلتر RO تكنولوجي 7 — RO Technology", "فلتر RO VIB", "فلتر RO Lexpure", "فلتر RO Future",
    "سيستم مركزي — فلتر مركزي رملي", "سيستم ميني", "فلتر شاور فيوتشر لايف", "أخرى / الموديل غير محدد",
]
MAINTENANCE_SERVICES = ["صيانة", "تبديل فلاتر", "تبديل قطع", "أخرى"]


def package_quantity(line: dict) -> int:
    """How many of the package this line was picked from: 1 for a product picked on its own."""
    try:
        value = int(float(str((line.get("details") or {}).get("package_quantity") or 1)))
    except ValueError:
        value = 1
    return value if line.get("group_id") and 0 < value <= MAX_PACKAGE_QUANTITY else 1


# Choices for a cooler's build, as staff already write them on Daftra work orders
FRONT_DESIGNS = ["مائل", "مستقيم"]
W_DIRECTIONS = ["عرضي", "طولي"]
COVER_BACKS = ["بدون ظهر", "باب W مفصلي"]
DESIGN_VERSIONS = ["تصميم جديد", "تصميم قديم حرف L"]
BASE_COLORS = ["أسود", "أبيض"]
# How many days an installation takes, i.e. the work order's delivery date after its start
INSTALLATION_DAYS = ["15", "20", "25"]


# ---------- Building blocks ----------

def f(name, label, type="text", required=False, **extra):
    return {"name": name, "label": label, "type": type, "required": required, **extra}


def money(name, label, required=False, **extra):
    return f(name, label, "number", required, min=0, **extra)


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
        f("area", "المنطقة", "select", required, options=AREAS, areas_by_emirate=AREAS_BY_EMIRATE),
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
        f("total_amount", total_label, "number", computed=["subtotal_amount", "discount_amount"],
          negative_message="قيمة الخصم أكبر من قيمة الطلب قبل الخصم")
        if computed_total else money("total_amount", total_label, True)
    )
    if auto_total:
        subtotal = [f("subtotal_amount", "قيمة الطلب النهائية قبل الخصم، شامل الضريبة والإضافات", "number", computed=[])]
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
        f("remaining_amount", remaining_label, "number", computed=["total_amount", "paid_amount"],
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
    f("inscription", "الكتابة المطلوبة (النص حرفيًا، أو «لا يوجد»)", "textarea", True),
    f("inscription_place", "مكان الكتابة، إن وجدت"),
]


# ---------- Forms ----------

FORM_TYPES = {
    "new_sale": {
        "label": "طلب بيع لعميل جديد",
        # Approving it creates the client (when new), the invoice and the receipt in Daftra
        "invoiced": True,
        "daftra_note": "ويُنشأ في دفترة العميل (إن كان جديدًا) والفاتورة وسند القبض بالمبلغ المدفوع، وأمر الشغل إن طُلب.",
        "sections": [
            request_info(invoiced=True),
            client(False),
            address(),
            section(
                "تفاصيل الطلب",
                f("order_lines", "المنتجات والباقات", "order_lines", True, subtotal_field="subtotal_amount", line_fields=[
                    # How many of the package: every product in it (and its inscription) counts this many times
                    f("package_quantity", "الكمية (عدد الباقات)", "number", integer=True, min=1, max=MAX_PACKAGE_QUANTITY,
                      package_only=True, stepper=True),
                    f("cooler_color", "لون البرادة", "select", True, options=COLORS),
                    # Its choices depend on the package (PACKAGE_COLOR_FAMILIES); optional, as its label says
                    f("cover_color", "لون الغطاء، إن يوجد", "package_color", optional=True,
                      families=[{**family, "colors": [shown for shown, _ in family["colors"]]} for family in PACKAGE_COLOR_FAMILIES]),
                    # The build details the work order's form in Daftra asks for
                    f("front_design", "تصميم القطعة الأمامية، إن ينطبق", "select", options=FRONT_DESIGNS),
                    f("w_direction", "اتجاه الدبليو، إن ينطبق", "select", options=W_DIRECTIONS),
                    f("cover_back", "ظهر الكفر، إن ينطبق", "select", options=COVER_BACKS),
                    f("design_version", "التصميم قديم أم جديد، إن ينطبق", "select", options=DESIGN_VERSIONS),
                    f("base_color", "لون القاعدة، إن ينطبق", "select", options=BASE_COLORS),
                    INSCRIPTION[0],
                    # beside: shown on the same line as that field, taking a third of it
                    money("inscription_price", "سعر الكتابة، شامل الضريبة (درهم)", required_if=HAS_INSCRIPTION,
                          charge=True, beside="inscription"),
                    f("manufacturing_notes", "ملاحظات خاصة للتصنيع", "textarea"),
                ]),
                note="إرسال الطلب يعني أن العميل وافق على التصميم واللون والكتابة.",
            ),
            amounts(must_pay=True, auto_total=True, invoiced=True),
            payment(invoiced=True),
            attachments(
                files("payment_proof", "إثبات الدفع", True),
                files("design_image", "صورة التصميم واللون المعتمدين", True),
                files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
            ),
            NOTES,
            section(
                "التركيب وأمر الشغل",
                yes_no("create_work_order", "إنشاء أمر الشغل في دفترة", default="نعم"),
                f("installation_days", "مدة التركيب (بالأيام)", "select", options=INSTALLATION_DAYS, required_if=WANTS_WORK_ORDER),
                note="عند الاعتماد يُنشأ أمر الشغل في دفترة والمدير المعتمِد مسؤولًا عنه، يبدأ يوم الاعتماد وينتهي بعد مدة التركيب، ويُربط بالفاتورة.",
            ),
        ],
    },
    "contract_renewal": {
        "label": "طلب تجديد عقد الصيانة السنوي",
        # Approving it updates the client's category and creates the renewal invoice and receipt in Daftra
        "invoiced": True,
        "daftra_note": "ويُحدَّث تصنيف العميل في دفترة، وتُنشأ فاتورة التجديد وسند القبض بالمبلغ المدفوع.",
        "sections": [
            request_info("تاريخ الطلب", invoiced=True),
            {**client(False), "note": "التجديد لعميل موجود في دفترة فقط؛ ابحث عنه برقم الهاتف أو الكود."},
            address(),
            section(
                "تفاصيل الطلب",
                f("cooler_type", "نوع البرادة", required=True),
                f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea"),
                note="الخدمة: تجديد عقد لمدة سنة، تبديل الفلاتر كل 3 شهور مع صيانة البرادة.",
            ),
            amounts(total_label="قيمة الطلب النهائية بعد الخصم، شامل الضريبة", must_pay=True, invoiced=True,
                    price_label="سعر تجديد العقد قبل الخصم، شامل الضريبة", price_default=RENEWAL_PRICE),
            payment(invoiced=True),
            attachments(files("payment_proof", "إثبات الدفع", True)),
            NOTES,
        ],
    },
    "maintenance": {
        "label": "طلب صيانة وتبديل",
        # Approving it creates the client (when new), the invoice with the chosen items, and the receipt
        "invoiced": True,
        "daftra_note": "ويُنشأ في دفترة العميل (إن كان جديدًا) وفاتورة البنود المختارة، وسند القبض إن وُجدت دفعة.",
        "sections": [
            request_info("تاريخ الطلب", invoiced=True),
            client(False),
            address(),
            section(
                "تفاصيل الطلب",
                f("devices", "نوع الجهاز / البرادة (يمكن اختيار أكثر من جهاز)", "multiselect", True,
                  options=MAINTENANCE_DEVICES, dropdown=True),
                f("service", "الخدمة", "select", True, options=MAINTENANCE_SERVICES, dropdown=True),
                # Only the catalog's maintenance items (products with a maintenance group), at their catalog price
                f("order_lines", "إضافة بند", "order_lines", True, subtotal_field="subtotal_amount", items="maintenance"),
                f("visit_date", "تاريخ الزيارة", "date", True),
            ),
            section(
                "قيمة الطلب",
                f("subtotal_amount", "قيمة البنود قبل الخصم، شامل الضريبة", "number", computed=[]),
                f("total_amount", "قيمة الطلب النهائية بعد الخصم، شامل الضريبة", "number",
                  computed=["subtotal_amount", "discount_amount"], negative_message="قيمة الخصم أكبر من قيمة البنود"),
                *discount_fields(),
                # A maintenance visit is paid in full (or is free: 0)
                money("paid_amount", "المبلغ المدفوع فعليًا الآن", True, must_equal="total_amount",
                      must_equal_message="يجب دفع قيمة الطلب كاملة"),
            ),
            section(
                "تفاصيل الدفعة",
                f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, required_if=PAID),
                f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury",
                  default_from={"field": "payment_method", "values": TREASURY_BY_METHOD}, required_if=PAID),
                f("payment_date", "تاريخ الدفع", "date", not_future=True, required_if=PAID),
                f("collector_name", "اسم المحصل، في حالة الدفع النقدي", "staff", required_if=CASH_PAYMENT),
            ),
            attachments(
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("work_media", "صور / فيديو العطل أو الأعمال المنفذة، إن توفرت"),
            ),
            NOTES,
        ],
    },
    "balance_payment": {
        "label": "طلب تسديد مبلغ متبقي",
        # Approving it creates a receipt in Daftra on the chosen invoice; nothing else is created
        "invoiced": True,
        "daftra_note": "ويُنشأ في دفترة سند قبض بالمبلغ المدفوع على الفاتورة المختارة.",
        "sections": [
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
                f("payment_date", "تاريخ التحصيل", "date", True, not_future=True),
                f("payment_reference", "رقم التحويل / السند الورقي", required=True),
            ),
            attachments(files("payment_proof", "صورة التحويل / الإيصال", True)),
            NOTES,
        ],
    },
    "quotation": {
        "label": "طلب عرض سعر",
        "sections": [
            request_info("تاريخ الطلب"),
            client(False, "اسم العميل / الجهة المطلوب على عرض السعر"),
            address("عنوان الخدمة — إن تم تحديده", required=False),
            section(
                "تفاصيل الطلب",
                f("product_name", "اسم المنتج / الخدمة والنسخة", "product", True),
                f("quantity", "الكمية", "number", True, min=1, integer=True, default="1"),
                f("outlets", "عدد المخارج، إن ينطبق", "number", min=1, max=12, integer=True),
                f("cover_color", "لون الغطاء، إن يوجد", "select", options=COLORS),
                f("cooler_color", "لون البرادة، إن ينطبق", "select", options=COLORS),
                f("dimensions", "المقاسات المطلوبة، إن تنطبق"),
                f("design", "التصميم المطلوب / مرجع صورته"),
                f("addons", "الإضافات المطلوبة، إن وجدت", "textarea"),
                *INSCRIPTION,
                f("special_requirements", "مواصفات أو متطلبات خاصة", "textarea"),
            ),
            section(
                "قيمة الطلب",
                money("quoted_price", "السعر المطلوب عرضه، شامل الضريبة والإضافات، إن تم تحديده"),
                money("discount_amount", "قيمة الخصم المقترح، إن وجد"),
                f("discount_approved", "هل الخصم معتمد؟", "select", True, options=["نعم", "لا", "لا يوجد خصم"]),
                f("discount_approved_by", "اسم الشخص الذي اعتمد الخصم، إن تم", "staff",
                  required_if={"field": "discount_approved", "equals": "نعم"}),
            ),
            section(
                "شروط السداد المقترحة",
                f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS),
                f("advance_payment", "قيمة / نسبة الدفعة المقدمة"),
                f("remaining_due", "موعد سداد المتبقي"),
                f("payment_terms", "أي شروط سداد خاصة", "textarea"),
            ),
            attachments(
                files("design_image", "صورة المنتج أو التصميم المطلوب، إن توفرت"),
                files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
                files("specification_file", "ملف مواصفات أو طلب الجهة، إن وجد"),
            ),
            NOTES,
        ],
    },
    "quote_to_invoice": {
        "label": "طلب تحويل عرض سعر إلى فاتورة",
        "sections": [
            request_info(),
            client(False, "اسم العميل / الجهة المطلوب على الفاتورة"),
            address("عنوان الخدمة — إذا تغيّر أو لم يُذكر في العرض", required=False),
            section(
                "تفاصيل الطلب",
                f("quotation_number", "رقم عرض السعر المطلوب تحويله", required=True),
                f("quotation_date", "تاريخ عرض السعر", "date", True, not_future=True),
                f("product_name", "المنتج / الخدمة المرتبط بها العرض", "product", True),
                yes_no("customer_approved", "هل العميل وافق على عرض السعر؟"),
                f("approval_date", "تاريخ موافقة العميل، إن تم", "date", not_future=True,
                  required_if={"field": "customer_approved", "equals": "نعم"}),
                yes_no("has_changes", "هل يوجد تغيير عن العرض؟"),
                f("change_details", "تفاصيل التغيير، إن وجد", "textarea",
                  required_if={"field": "has_changes", "equals": "نعم"}),
                f("conversion_approved_by", "اسم المسؤول الذي اعتمد التحويل، إن تم", "staff"),
                yes_no("statement_needed", "هل مطلوب إرسال كشف حساب؟"),
            ),
            amounts(discount_label="خصم إضافي عن عرض السعر، إن وجد"),
            payment("تفاصيل الدفعة — إن وُجدت دفعة", when=PAID),
            attachments(
                files("quotation_file", "عرض السعر المطلوب تحويله", True),
                files("approval_proof", "إثبات موافقة العميل، إن توفر"),
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("design_image", "التصميم أو المواصفات المعدّلة، إن وجدت"),
            ),
            NOTES,
        ],
    },
    "order_addition": {
        "label": "طلب إضافة على طلب قائم",
        "sections": [
            request_info(),
            client(True),
            address(),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("product_name", "المنتج / الخدمة المرتبط بها الإضافة", "product", True),
                f("addition_details", "الإضافة المطلوبة بالتفصيل", "textarea", True),
                f("quantity_unit", "الكمية / الطول والوحدة", required=True),
                money("unit_price", "سعر الوحدة المتفق عليه، إن ينطبق"),
                f("specifications", "اللون / المقاسات / المواصفات، إن تنطبق"),
                *INSCRIPTION,
                yes_no("customer_approved", "هل العميل وافق على مواصفات الإضافة وتكلفتها؟"),
                f("addition_status", "حالة الإضافة", "select", True, options=WORK_STATUS),
                f("execution_info", "تاريخ التنفيذ واسم الفني، إن تم",
                  required_if={"field": "addition_status", "in": WORK_STARTED}),
            ),
            amounts(
                total_label="قيمة الإضافة النهائية بعد الخصم، شامل الضريبة",
                discount_label="قيمة الخصم على الإضافة، إن وجد",
                paid_label="المبلغ المدفوع فعليًا الآن مقابل الإضافة",
                remaining_label="المبلغ المتبقي من قيمة الإضافة",
            ),
            payment(when=PAID),
            attachments(
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت"),
                files("design_image", "صورة التصميم أو الإضافة المتفق عليها، إن توفرت"),
                files("inscription_file", "صورة / ملف الكتابة، إن وجدت"),
            ),
            NOTES,
        ],
    },
    "order_modification": {
        "label": "طلب تعديل على طلب قائم",
        "sections": [
            request_info(),
            client(True),
            address("عنوان الخدمة — إذا كان التعديل يخص العنوان", required=False),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("product_name", "المنتج / الخدمة المرتبط بها التعديل", "product", True),
                f("modified_items", "المطلوب تعديله", "multiselect", True,
                  options=["بيانات العميل", "العنوان", "المنتج", "الكمية", "اللون", "التصميم", "الكتابة", "السعر", "أخرى"]),
                f("before_change", "البيانات أو المواصفات قبل التعديل", "textarea", True),
                f("after_change", "البيانات أو المواصفات المطلوبة بعد التعديل", "textarea", True),
                f("change_reason", "سبب التعديل", "textarea", True),
                f("execution_status", "حالة تنفيذ الطلب", "select", True,
                  options=["لم يبدأ", "قيد التنفيذ", "تم التنفيذ", "غير معروف"]),
                yes_no("customer_approved", "هل العميل وافق على التعديل وتكلفته؟"),
                f("change_approved_by", "اسم المسؤول الذي اعتمد التعديل، إن تم اعتماده", "staff"),
            ),
            section(
                "قيمة الطلب",
                f("value_change", "هل التعديل يغيّر قيمة الطلب؟", "select", True,
                  options=["زيادة", "تخفيض", "بدون تغيير", "تحتاج مراجعة"]),
                money("total_before", "قيمة الطلب النهائية قبل التعديل", True),
                money("total_amount", "قيمة الطلب النهائية بعد التعديل، شامل الضريبة والإضافات", True),
                *discount_fields("خصم إضافي مرتبط بالتعديل، إن وجد"),
                money("paid_amount", "المبلغ المدفوع فعليًا الآن", True),
                money("remaining_amount", "المبلغ المتبقي بعد التعديل", True),
                f("remaining_due_date", "موعد سداد المتبقي، إن وجد", "date"),
            ),
            payment("تفاصيل الدفعة — إن وُجدت دفعة جديدة", when=PAID),
            attachments(
                files("invoice_image", "صورة الفاتورة / الطلب الأصلي، إن توفرت"),
                files("design_image", "صورة التصميم أو المواصفات الجديدة، إن تنطبق"),
                files("inscription_file", "صورة / ملف الكتابة الجديدة، إن وجدت"),
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة جديدة", required_if=PAID),
            ),
            NOTES,
        ],
    },
    "return_refund": {
        "label": "طلب مرتجع ورد مبلغ",
        "sections": [
            request_info(),
            client(True),
            address("عنوان الخدمة / استلام المرتجع"),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("return_type", "نوع المرتجع", "select", True, options=["كامل الطلب", "جزء من الطلب"]),
                f("returned_items", "المنتج / الأصناف المطلوب إرجاعها", "textarea", True),
                f("returned_quantities", "الكمية المرتجعة من كل صنف", "textarea", True),
                f("return_reason", "سبب المرتجع", "textarea", True),
                f("product_condition", "حالة المنتج وملاحظات عليه", "textarea", True),
                f("receipt_status", "حالة استلام المرتجع", "select", True, options=["لم يُستلم", "تم الاستلام"]),
                f("receipt_date", "تاريخ الاستلام، إن تم", "date", not_future=True,
                  required_if={"field": "receipt_status", "equals": "تم الاستلام"}),
                f("received_by", "اسم الموظف الذي استلم المرتجع، إن تم", "staff",
                  required_if={"field": "receipt_status", "equals": "تم الاستلام"}),
                f("return_approved_by", "اسم المسؤول الذي اعتمد المرتجع، إن تم اعتماده", "staff"),
            ),
            section(
                "قيمة الطلب",
                money("invoice_total", "قيمة الطلب النهائية المسجلة على الفاتورة", True),
                money("total_paid", "إجمالي المبلغ المدفوع على الطلب الأصلي", True),
                money("returned_value", "قيمة الأصناف المرتجعة حسب الفاتورة", True),
                money("deduction_amount", "قيمة أي استقطاع أو رسوم مرتبطة بالمرتجع، إن وجدت"),
                f("deduction_reason", "سبب الاستقطاع واسم المسؤول الذي اعتمده",
                  required_if={"field": "deduction_amount", "gt": 0}),
                money("approved_refund", "المبلغ المعتمد رده للعميل، إن تم تحديده"),
                f("refund_approved_by", "اسم المسؤول الذي اعتمد مبلغ الرد", "staff",
                  required_if={"field": "approved_refund", "gt": 0}),
                money("refunded_amount", "المبلغ المردود فعليًا الآن", True),
                f("refund_remaining", "المبلغ المتبقي من مبلغ الرد المعتمد", "number",
                  computed=["approved_refund", "refunded_amount"],
                  negative_message="المبلغ المردود أكبر من مبلغ الرد المعتمد"),
                f("refund_remaining_date", "موعد رد المتبقي، إن تم تحديده", "date"),
            ),
            section(
                "تفاصيل رد المبلغ — إن تم",
                f("refund_method", "طريقة رد المبلغ", "select", options=REFUND_METHODS,
                  required_if={"field": "refunded_amount", "gt": 0}),
                f("refund_date", "تاريخ رد المبلغ", "date", not_future=True,
                  required_if={"field": "refunded_amount", "gt": 0}),
                f("refund_reference", "رقم التحويل / مرجع عملية الرد / السند",
                  required_if={"field": "refunded_amount", "gt": 0}),
                f("refund_paid_by", "اسم الموظف الذي سلّم المبلغ، في حالة الرد النقدي", "staff",
                  required_if={"field": "refund_method", "equals": CASH}),
            ),
            attachments(
                files("invoice_image", "صورة الفاتورة الأصلية، إن توفرت"),
                files("product_photos", "صور المنتج المرتجع وحالته", True),
                files("receipt_proof", "إثبات استلام المرتجع، إن تم",
                      required_if={"field": "receipt_status", "equals": "تم الاستلام"}),
                files("refund_proof", "إثبات رد المبلغ، إن تم", required_if={"field": "refunded_amount", "gt": 0}),
            ),
            NOTES,
        ],
    },
    "tech_cash_collection": {
        "label": "تسجيل تحصيل نقدي بواسطة الفني",
        "sections": [
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
                f("payment_date", "تاريخ الدفع", "date", True, not_future=True),
                f("paper_receipt_number", "رقم سند القبض الورقي", required=True),
                f("technician_name", "اسم الفني المحصل", "staff", required=True),
            ),
            attachments(
                files("receipt_image", "صورة سند القبض الورقي", True),
                files("invoice_image", "صورة الفاتورة المرتبطة، إن توفرت"),
            ),
            NOTES,
        ],
    },
    # ---------- Drafted from the design's form catalog; fields to be confirmed by the business ----------
    "reinstallation": {
        "label": "طلب إعادة تركيب",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            address("عنوان التركيب الجديد"),
            section(
                "تفاصيل الطلب",
                *original_refs(),
                f("product_name", "المنتج / الجهاز المطلوب إعادة تركيبه", "product", True),
                f("reinstall_reason", "سبب إعادة التركيب", "select", True,
                  options=["نقل إلى عنوان جديد", "إعادة تركيب بعد صيانة", "تركيب سابق غير سليم", "أخرى"]),
                f("reason_details", "تفاصيل السبب", "textarea", True),
                f("current_location", "مكان الجهاز الحالي، إن اختلف عن العنوان الجديد"),
                f("preferred_date", "الموعد المفضل للتركيب", "date"),
                f("extra_works", "أعمال إضافية مطلوبة، إن وجدت (تمديدات، قاعدة، فك)", "textarea"),
            ),
            section(
                "قيمة الطلب",
                f("coverage", "تغطية الخدمة", "select", True, options=["مدفوعة", "مجانية / مشمولة", "تحتاج مراجعة"]),
                money("total_amount", "قيمة الخدمة شامل الضريبة", required_if={"field": "coverage", "equals": "مدفوعة"}),
                money("paid_amount", "المبلغ المدفوع فعليًا الآن"),
            ),
            payment(when=PAID),
            attachments(
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
                files("site_photos", "صور الموقع الجديد، إن توفرت"),
            ),
            NOTES,
        ],
    },
    "data_entry_error": {
        "label": "تبليغ خطأ إدخال بيانات",
        "sections": [
            request_info("تاريخ التبليغ"),
            client(False, "اسم العميل"),
            section(
                "تفاصيل الخطأ",
                f("document_type", "المستند الذي فيه الخطأ", "select", True,
                  options=["فاتورة", "سند قبض", "عرض سعر", "أمر شغل", "بيانات عميل", "أخرى"]),
                f("document_number", "رقم المستند", required=True),
                f("error_field", "البيان الخطأ (مثل: اسم العميل، المبلغ، التاريخ)", required=True),
                f("wrong_value", "القيمة المسجلة الخطأ", "textarea", True),
                f("correct_value", "القيمة الصحيحة", "textarea", True),
                f("urgency", "الأولوية", "select", True, options=["عادي", "عاجل"]),
            ),
            attachments(
                files("document_image", "صورة المستند الذي فيه الخطأ، إن توفرت"),
                files("evidence", "ما يثبت القيمة الصحيحة، إن توفر"),
            ),
            NOTES,
        ],
    },
    "pre_sale_inspection": {
        "label": "طلب معاينة قبل البيع",
        "sections": [
            request_info("تاريخ الطلب"),
            client(False, "اسم العميل / الجهة"),
            address("عنوان المعاينة"),
            section(
                "تفاصيل الطلب",
                f("site_type", "نوع الموقع", "select", True,
                  options=["منزل", "مسجد", "مدرسة", "مغسلة سيارات", "جمعية خيرية", "شركة", "أخرى"]),
                f("product_name", "المنتج المبدئي المهتم به العميل، إن وجد", "product"),
                f("inspection_purpose", "المطلوب من المعاينة", "textarea", True),
                f("preferred_date", "الموعد المفضل للمعاينة", "date"),
                f("preferred_time", "الوقت المفضل", "select", options=["صباحًا", "ظهرًا", "مساءً"]),
                f("site_contact", "اسم ورقم الشخص المسؤول في الموقع، إن اختلف عن العميل"),
            ),
            attachments(files("site_photos", "صور الموقع، إن توفرت")),
            NOTES,
        ],
    },
    "installation_completed": {
        "label": "تأكيد إتمام التركيب",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل التركيب",
                f("work_order", "رقم أمر الشغل", required=True),
                f("invoice_number", "رقم الفاتورة، إن توفر"),
                f("product_name", "المنتج الذي تم تركيبه", "product", True),
                f("installation_date", "تاريخ التركيب", "date", True, not_future=True),
                f("technician_name", "اسم الفني", "staff", required=True),
                f("installation_status", "حالة التركيب", "select", True, options=["تم بالكامل", "تم مع ملاحظات"]),
                f("issues", "الملاحظات على التركيب", "textarea",
                  required_if={"field": "installation_status", "equals": "تم مع ملاحظات"}),
                yes_no("extra_work", "هل نُفذت أعمال إضافية؟"),
                f("extra_work_details", "تفاصيل الأعمال الإضافية", "textarea", required_if={"field": "extra_work", "equals": "نعم"}),
                yes_no("customer_signed", "هل وقّع العميل على استلام التركيب؟"),
            ),
            section(
                "التحصيل عند التركيب",
                money("paid_amount", "المبلغ المحصل عند التركيب، إن وجد"),
                f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, required_if=PAID),
                f("payment_reference", "رقم التحويل / السند الورقي", required_if=PAID),
            ),
            attachments(
                files("installation_photos", "صور التركيب بعد الانتهاء", True),
                files("signed_work_order", "صورة أمر الشغل الموقّع، إن توفرت"),
                files("payment_proof", "إثبات الدفع، إن وُجد تحصيل", required_if=PAID),
            ),
            NOTES,
        ],
    },
    "contract_service_done": {
        "label": "تأكيد إنجاز خدمة مشمولة بالعقد",
        "sections": [
            request_info("تاريخ الطلب"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل الخدمة",
                f("contract_number", "رقم العقد / الفاتورة", required=True),
                f("visit_number", "رقم الزيارة في العقد", "select", True,
                  options=["الزيارة الأولى", "الزيارة الثانية", "الزيارة الثالثة", "الزيارة الرابعة", "زيارة إضافية"]),
                f("services_done", "الخدمات المنفذة", "multiselect", True,
                  options=["تبديل فلاتر", "صيانة البرادة", "تنظيف", "فحص"]),
                f("service_date", "تاريخ التنفيذ", "date", True, not_future=True),
                f("technician_name", "اسم الفني", "staff", required=True),
                f("parts", "القطع والفلاتر المستبدلة وكمياتها", "textarea"),
                f("cooler_notes", "ملاحظات على حالة البرادة، إن وجدت", "textarea"),
                f("next_visit_date", "موعد الزيارة القادمة، إن تحدد", "date"),
            ),
            attachments(
                files("service_photos", "صور قبل وبعد الخدمة، إن توفرت"),
                files("signed_report", "تقرير الزيارة الموقّع، إن توفر"),
            ),
            NOTES,
        ],
    },
    "open_ticket": {
        "label": "فتح بلاغ صيانة وأعطال",
        "sections": [
            request_info("تاريخ البلاغ"),
            client(False, "اسم العميل"),
            address(),
            section(
                "تفاصيل البلاغ",
                f("device_type", "الجهاز / البرادة", required=True),
                f("related_number", "رقم العقد أو الفاتورة المرتبطة، إن توفر"),
                f("problem", "وصف العطل كما ذكره العميل", "textarea", True),
                f("coverage", "تغطية الإصلاح", "select", True, options=["ضمان", "عقد صيانة", "مدفوع", "غير معروف"]),
                f("urgency", "الأولوية", "select", True, options=["عادي", "عاجل", "طارئ"]),
                f("preferred_date", "الموعد المفضل للزيارة، إن وجد", "date"),
            ),
            attachments(files("fault_media", "صور / فيديو العطل، إن توفرت")),
            NOTES,
        ],
    },
    "close_ticket": {
        "label": "إغلاق بلاغ صيانة وأعطال",
        "sections": [
            request_info("تاريخ الإغلاق"),
            client(True, "اسم العميل"),
            section(
                "تفاصيل الإغلاق",
                f("ticket_number", "رقم البلاغ / الطلب الأصلي", required=True),
                f("visit_date", "تاريخ الزيارة", "date", True, not_future=True),
                f("technician_name", "اسم الفني", "staff", required=True),
                f("resolution", "نتيجة الزيارة", "select", True,
                  options=["تم الإصلاح", "تم استبدال قطع", "يحتاج زيارة أخرى", "تعذر الإصلاح"]),
                f("work_details", "الأعمال المنفذة بالتفصيل", "textarea", True),
                f("parts", "القطع المستبدلة وكمياتها، إن وجدت", "textarea"),
                f("follow_up_date", "موعد الزيارة التالية", "date", required_if={"field": "resolution", "equals": "يحتاج زيارة أخرى"}),
            ),
            section(
                "قيمة الطلب",
                f("coverage", "تغطية الإصلاح", "select", True, options=["مشمول بعقد أو ضمان", "مدفوع"]),
                money("total_amount", "قيمة الإصلاح شامل الضريبة", required_if={"field": "coverage", "equals": "مدفوع"}),
                money("paid_amount", "المبلغ المدفوع فعليًا الآن"),
            ),
            payment(when=PAID),
            attachments(
                files("after_photos", "صور بعد الإصلاح، إن توفرت"),
                files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
            ),
            NOTES,
        ],
    },
    "daily_visits": {
        "label": "تقرير الزيارات اليومي",
        "sections": [
            section(
                "بيانات التقرير",
                f("request_date", "تاريخ التقرير", "date", True, default="today", not_future=True),
                f("employee_name", "اسم الموظف", "auto_user"),
                f("visit_area", "المنطقة / خط السير"),
            ),
            section(
                "الزيارات",
                f("visits_count", "عدد الزيارات", "number", True, min=1, integer=True),
                f("visits", "تفاصيل الزيارات: لكل زيارة سطر فيه العميل والمنطقة والغرض والنتيجة", "textarea", True, max_length=6000),
                f("new_leads", "عدد العملاء المهتمين الجدد", "number", min=0, integer=True),
                f("closed_sales", "عدد المبيعات المؤكدة", "number", min=0, integer=True),
                money("collected_amount", "إجمالي المبالغ المحصلة، إن وجدت"),
                f("issues", "مشاكل أو طلبات تحتاج متابعة", "textarea"),
            ),
            attachments(files("visit_photos", "صور من الزيارات، إن توفرت")),
            NOTES,
        ],
    },
}


# ---------- Validation ----------

# The forms a new request can be made from. The others stay defined (requests already made with
# them still open, show and can be reviewed) but are hidden; add a key here to bring one back.
VISIBLE_FORM_TYPES = {"new_sale", "contract_renewal", "balance_payment", "maintenance"}


def list_form_types() -> list[dict]:
    return [{"key": key, **definition, "hidden": key not in VISIBLE_FORM_TYPES} for key, definition in FORM_TYPES.items()]


def form_fields(form_type: str) -> list[dict]:
    return [spec for s in FORM_TYPES[form_type]["sections"] for spec in s["fields"]]


def is_input(spec: dict) -> bool:
    """True for fields the user types into (not uploads, computed or automatic ones)."""
    return spec["type"] not in ("files", "auto_user") and "computed" not in spec


def _clean_value(spec: dict, raw):
    """Returns (value, error) for one input field. An empty value comes back as None."""
    kind = spec["type"]
    if kind == "multiselect":
        chosen = [v for v in raw if v in spec["options"]] if isinstance(raw, list) else []
        return (chosen or None), None
    if kind == "order_lines":
        lines = []
        for line in raw if isinstance(raw, list) else []:
            line = line or {}
            product_id = str(line.get("product_id") or "").strip()
            try:
                quantity = int(line.get("quantity"))
            except (TypeError, ValueError):
                quantity = 0
            if product_id and quantity > 0:
                package_id = str(line.get("package_id") or "").strip()
                lines.append({
                    "product_id": product_id, "name": str(line.get("name") or "")[:200], "quantity": quantity,
                    # Lines picked from the same package keep this, so the form can group them back together
                    "group_id": str(line["group_id"])[:40] if line.get("group_id") else None,
                    "group_name": str(line.get("group_name") or "")[:200],
                    # The package the line was picked from, which sets its price (see validate_submission)
                    "package_id": package_id if package_id.isdigit() else None,
                    "base_quantity": int(line["base_quantity"]) if str(line.get("base_quantity") or "").isdigit() else None,
                    # Raw per-line fields (e.g. design, cooler colour); validated in validate_submission,
                    # against this field's own "line_fields", since each line needs its own errors
                    "details": line.get("details") if isinstance(line.get("details"), dict) else {},
                })
        return (lines or None), None

    value = "" if raw is None or isinstance(raw, (list, dict)) else str(raw).strip()
    if value == "":
        return None, None

    if kind == "number":
        try:
            number = float(value.translate(ARABIC_DIGITS).replace(",", ""))
        except ValueError:
            return None, "أدخل رقمًا صحيحًا"
        if spec.get("integer") and not number.is_integer():
            return None, "أدخل عددًا بدون كسور"
        if spec.get("positive") and number <= 0:
            return None, "يجب أن يكون أكبر من صفر"
        if "min" in spec and number < spec["min"]:
            return None, f"الحد الأدنى {spec['min']}"
        if "max" in spec and number > spec["max"]:
            return None, f"الحد الأقصى {spec['max']}"
        return (int(number) if spec.get("integer") else round(number, 2)), None
    if kind == "phone":
        value = re.sub(r"[\s\-()]", "", value.translate(ARABIC_DIGITS))
        return (value, None) if PHONE_RE.match(value) else (None, "أدخل رقم هاتف إماراتي صحيح")
    if kind == "date":
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None, "أدخل تاريخًا صحيحًا"
        if spec.get("not_future") and parsed > date.today():
            return None, "التاريخ لا يمكن أن يكون في المستقبل"
        return value, None
    if kind == "select":
        return (value, None) if value in spec["options"] else (None, "اختر من القائمة")
    if kind in DAFTRA_LIST_TYPES:
        # Checked against Daftra's list in validate_submission, when the list could be loaded
        return (int(value), None) if value.isdigit() else (None, "اختر من القائمة")

    if len(value) > spec.get("max_length", DEFAULT_MAX_LENGTH[kind]):
        return None, f"الحد الأقصى {spec.get('max_length', DEFAULT_MAX_LENGTH[kind])} حرفًا"
    if "pattern" in spec:
        value = value.translate(ARABIC_DIGITS)
        if not re.match(spec["pattern"], value):
            return None, spec.get("pattern_message", "صيغة غير صحيحة")
    return value, None


def _condition_met(condition: dict, clean: dict) -> bool:
    value = clean.get(condition["field"])
    if "equals" in condition:
        return value == condition["equals"]
    if "in" in condition:
        return value in condition["in"]
    if "not_in" in condition:
        return value not in condition["not_in"]
    return isinstance(value, (int, float)) and value > condition["gt"]


def validate_submission(form_type: str, data: dict, file_counts: dict, employee_name: str,
                        products: dict | None = None, package_prices: dict | None = None,
                        daftra_lists: dict | None = None) -> tuple[dict, dict]:
    """Returns (clean_data, errors) where errors maps field name to message.

    products maps our catalog's product id to product; None means the list could not be loaded,
    in which case the product the user picked is accepted as sent.
    package_prices maps (package id, product id) to the product's unit price inside that package.
    daftra_lists maps a DAFTRA_LIST_TYPES type to {id: name} of Daftra's list; a type missing from
    it could not be loaded, so its id is accepted as sent and Daftra checks it on approval.
    """
    fields = form_fields(form_type)
    clean, errors = {}, {}

    for spec in filter(is_input, fields):
        value, error = _clean_value(spec, data.get(spec["name"]))
        if error:
            errors[spec["name"]] = error
        elif value is not None:
            clean[spec["name"]] = value

    for spec in fields:
        name = spec["name"]
        if spec["type"] != "product" or name not in clean:
            continue
        product_id = str(data.get(name + "_id") or "").strip()
        product = products.get(product_id) if products is not None else None
        if products is not None and product is None:
            del clean[name]
            errors[name] = "اختر المنتج من القائمة"
        elif product_id:
            clean[name + "_id"] = product_id
            if product:
                clean[name] = product["name"]

    for spec in fields:
        name = spec["name"]
        if spec["type"] != "order_lines" or name not in clean:
            continue
        line_fields = spec.get("line_fields", [])
        charges = [dspec["name"] for dspec in line_fields if dspec.get("charge")]
        resolved = []
        line_errors = {}
        subtotal = 0.0
        seen_groups = set()
        for index, line in enumerate(clean[name]):
            product = products.get(line["product_id"]) if products is not None else None
            if products is not None and product is None:
                continue
            # A field offering only maintenance items takes nothing else, whatever the browser sends
            if spec.get("items") == "maintenance" and product is not None and not product.get("maintenance_group"):
                continue
            # The price is looked up here, never taken from the browser: a product's price inside the
            # package it was picked from, else its own catalog price
            price = None
            if line["package_id"] and package_prices is not None:
                price = package_prices.get((line["package_id"], line["product_id"]))
            if price is None and product:
                price = product.get("price") or 0
            # A package's «الكمية» is already in its products' quantities; its charges (the inscription) are per package
            count = package_quantity(line)
            subtotal += (price or 0) * line["quantity"]
            details, row_errors = {}, {}
            for dspec in filter(is_input, line_fields):
                dvalue, derror = _clean_value(dspec, line["details"].get(dspec["name"]))
                if derror:
                    row_errors[dspec["name"]] = derror
                elif dvalue is not None:
                    details[dspec["name"]] = dvalue
            for dspec in line_fields:
                dname = dspec["name"]
                required = dspec["required"] or ("required_if" in dspec and _condition_met(dspec["required_if"], details))
                if dspec["type"] == "package_color":
                    # The package (or the product picked on its own) decides the choices, and whether there are any
                    allowed = [shown for shown, _ in package_colors(line.get("group_name") or line.get("name"))]
                    required = bool(allowed) and not dspec.get("optional")
                    if dname in details and details[dname] not in allowed:
                        if allowed:
                            row_errors[dname] = "اختر من القائمة"
                        del details[dname]
                if required and dname not in details and dname not in row_errors:
                    row_errors[dname] = "مطلوب"
            if row_errors:
                line_errors[str(len(resolved))] = row_errors
            # A package's details are copied onto each of its lines, so its charges count once
            if not line.get("group_id") or line["group_id"] not in seen_groups:
                subtotal += sum(details.get(charge) or 0 for charge in charges) * count
            if line.get("group_id"):
                seen_groups.add(line["group_id"])
            resolved.append({
                "product_id": line["product_id"], "name": product["name"] if product else line["name"],
                "quantity": line["quantity"], "group_id": line.get("group_id"), "group_name": line.get("group_name"),
                "package_id": line["package_id"], "base_quantity": line.get("base_quantity"), "unit_price": price,
                "details": details,
            })
        if not resolved:
            del clean[name]
            errors[name] = "اختر منتجًا أو باقة واحدة على الأقل"
        else:
            clean[name] = resolved
            if line_errors:
                errors[name] = {"lines": line_errors}
            # The field named here shows this total, worked out from each line's catalog price
            if spec.get("subtotal_field") and products is not None:
                clean[spec["subtotal_field"]] = round(subtotal, 2)

    for spec in fields:
        name = spec["name"]
        options = (daftra_lists or {}).get(spec["type"])
        if spec["type"] not in DAFTRA_LIST_TYPES or name not in clean or options is None:
            continue
        if clean[name] in options:
            clean[name + "_name"] = options[clean[name]]
        else:
            del clean[name]
            errors[name] = "اختر من القائمة"

    for spec in fields:
        name = spec["name"]
        if spec["type"] == "auto_user":
            clean[name] = employee_name
        elif "computed" in spec:
            # Already set by something else (e.g. order_lines' subtotal_field); nothing to subtract here
            if name in clean or not spec["computed"]:
                continue
            first, *rest = (clean.get(operand) for operand in spec["computed"])
            if first is not None:
                result = round(first - sum(v or 0 for v in rest), 2)
                if result < 0:
                    errors[name] = spec["negative_message"]
                else:
                    clean[name] = result

    # A field that must equal another (e.g. the amount paid must be the whole total)
    for spec in fields:
        other = spec.get("must_equal")
        if other and spec["name"] in clean and other in clean and spec["name"] not in errors:
            if abs(clean[spec["name"]] - clean[other]) > 0.005:
                errors[spec["name"]] = spec.get("must_equal_message") or "القيمتان يجب أن تتساويا"

    for spec in fields:
        name = spec["name"]
        required = spec["required"] or ("required_if" in spec and _condition_met(spec["required_if"], clean))
        if not required or name in errors:
            continue
        if spec["type"] == "files":
            if not file_counts.get(name):
                errors[name] = "أرفق ملفًا واحدًا على الأقل"
        elif is_input(spec) and name not in clean:
            errors[name] = "مطلوب"
    return clean, errors


def sanitize_draft(form_type: str, data: dict) -> dict:
    """Drafts are stored as typed, without validation, so the user can finish them later."""
    draft = {}
    for spec in filter(is_input, form_fields(form_type)):
        raw = data.get(spec["name"])
        if spec["type"] == "order_lines":
            lines = [
                {"product_id": str(line.get("product_id"))[:20], "name": str(line.get("name") or "")[:200],
                 "quantity": int(line["quantity"]) if str(line.get("quantity", "")).strip().isdigit() else 1,
                 "group_id": str(line["group_id"])[:40] if line.get("group_id") else None,
                 "group_name": str(line.get("group_name") or "")[:200],
                 "package_id": str(line["package_id"])[:20] if str(line.get("package_id") or "").isdigit() else None,
                 "base_quantity": int(line["base_quantity"]) if str(line.get("base_quantity") or "").isdigit() else None,
                 # Shown again when the draft is opened; worked out afresh when it is submitted
                 "unit_price": line["unit_price"] if isinstance(line.get("unit_price"), (int, float)) else None,
                 "details": {
                     str(k)[:40]: str(v)[:2000] for k, v in (line.get("details") or {}).items()
                     if isinstance(line.get("details"), dict) and not isinstance(v, (list, dict))
                 }}
                for line in (raw if isinstance(raw, list) else [])[:100]
                if isinstance(line, dict) and line.get("product_id")
            ]
            if lines:
                draft[spec["name"]] = lines
            continue
        if isinstance(raw, list):
            value = [str(v)[:200] for v in raw[:50]]
        else:
            value = "" if raw is None or isinstance(raw, dict) else str(raw)[:5000]
        if value:
            draft[spec["name"]] = value
            if spec["type"] == "product" and data.get(spec["name"] + "_id"):
                draft[spec["name"] + "_id"] = str(data[spec["name"] + "_id"])[:20]
            if spec["type"] in DAFTRA_LIST_TYPES and data.get(spec["name"] + "_name"):
                draft[spec["name"] + "_name"] = str(data[spec["name"] + "_name"])[:200]
    return draft
