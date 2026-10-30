"""The fields of طلب بيع لعميل جديد, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    COLORS,
    INSCRIPTION,
    INSTALLATION_WORK,
    NO_INSCRIPTION,
    MAX_PACKAGE_QUANTITY,
    NOTES,
    PACKAGE_COLOR_FAMILIES,
    address,
    amounts,
    attachments,
    client,
    f,
    files,
    money,
    payment,
    request_info,
    section,
    yes_no,
)

# Choices only this form offers
HAS_INSCRIPTION = {"field": "inscription", "not_in": NO_INSCRIPTION}

WANTS_WORK_ORDER = {"field": "create_work_order", "equals": "نعم"}

# Choices for a cooler's build, as staff already write them on Daftra work orders
FRONT_DESIGNS = ["مائل", "مستقيم"]

W_DIRECTIONS = ["عرضي", "طولي"]

COVER_BACKS = [
    "بدون ظهر",
    "باب W مفصلي",
    "ظهر الكفر بدون ظهر",
    "ظهر كلادينج ثابت",
    "باب كلادينج مفصلي",
    "باب W جرار",
    "باب كلادينج جرار",
    "ظهر الالمنيوم لوفر ثابت",
    "باب الالمنيوم لوفر مفصلي",
    "باب الالمنيوم لوفر جرار",
]

DESIGN_VERSIONS = [
    "تصميم جديد",
    "تصميم قديم حرف L",
    "تصميم قديم مستطيل",
]

BASE_COLORS = ["أسود", "أبيض", "الرصاصي"]

# How many days an installation takes, i.e. the work order's delivery date after its start
# The longest مدة التركيب a work order can be given, in days
MAX_INSTALLATION_DAYS = 365

SECTIONS = [
    request_info(invoiced=True),
    client(False, creates_client=True),
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
            # What installing it involves, printed on the work order as ملحقات التركيب. The package
            # picked fills it in (default_by_package); the salesperson may add to it or empty it.
            f("installation_accessories", "ملحقات التركيب والأعمال المطلوبة", "textarea",
              default_by_package=INSTALLATION_WORK),
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
        yes_no("create_work_order", "إنشاء أمر الشغل في دفترة"),
        # Any whole number of days (e.g. 15, 20, 17): the work order is due that many days after approval
        f("installation_days", "مدة التركيب (بالأيام)", "number", integer=True, min=1, max=MAX_INSTALLATION_DAYS,
          placeholder="مثال: 15 أو 20", unit="يومًا", required_if=WANTS_WORK_ORDER),
        note="عند الاعتماد يُنشأ أمر الشغل في دفترة والمدير المعتمِد مسؤولًا عنه، يبدأ يوم الاعتماد وينتهي بعد مدة التركيب، ويُربط بالفاتورة.",
    ),
]
