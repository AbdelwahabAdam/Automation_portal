"""What طلب بيع لعميل جديد asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds

`shared.x(...)` is a section many forms use (form_engine/sections.py); the functions written
below are this form's own. Changing what this form asks is changing one switch here — and its
snapshot (tests/forms/snapshots/new_sale.json) on purpose with it.
"""

from ...modules.form_engine import (
    CASH_PAYMENT,
    COLORS,
    DISCOUNTED,
    HAS_REMAINDER,
    HIDE,
    INSCRIPTION,
    INSTALLATION_WORK,
    MAX_PACKAGE_QUANTITY,
    NEW_CLIENT,
    NO_INSCRIPTION,
    OPEN_PRICE_FIELDS,
    PACKAGE_COLOR_FAMILIES,
    PACKAGE_INSCRIPTIONS,
    PLATE_COLORS,
    REQUIRED,
    REQUIRED_IF,
    SHOW,
    f,
    files,
    money,
    shared,
    switched,
    switched_fields,
    yes_no,
)

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
# What a cooler has when nothing else is chosen, and what the work order carries then
NO_COVER_BACK = COVER_BACKS[0]

DESIGN_VERSIONS = [
    "تصميم جديد",
    "تصميم قديم حرف L",
    "تصميم قديم مستطيل",
]

BASE_COLORS = ["أسود", "أبيض", "الرصاصي"]

# The longest مدة التركيب a work order can be given, in days
MAX_INSTALLATION_DAYS = 365

[ITEM_PRICE, WORK_DESCRIPTION] = OPEN_PRICE_FIELDS


# ---------- this form's own sections ----------

def order_details(*, order_lines, package_quantity, cooler_color, cover_color, plate_color, front_design,
                  w_direction, cover_back, design_version, base_color, inscription, inscription_price,
                  manufacturing_notes, installation_accessories, item_price, work_description):
    """تفاصيل الطلب: the products and packages, and what each package is to look like.

    Every switch but order_lines is a field of each line, asked once per package.
    """
    lines = switched_fields(
        # How many of the package: every product in it (and its inscription) counts this many times
        (package_quantity, f("package_quantity", "الكمية (عدد الباقات)", "number", integer=True, min=1,
                             max=MAX_PACKAGE_QUANTITY, package_only=True, stepper=True)),
        (cooler_color, f("cooler_color", "لون البرادة", "select", options=COLORS)),
        # Its own colours where the package has them (PACKAGE_COLOR_FAMILIES), the six plain ones where
        # it has none. Optional, as its label says.
        (cover_color, f("cover_color", "لون الغطاء، إن يوجد", "package_color", optional=True,
                        default_colors=PLATE_COLORS,
                        families=[{**family, "colors": [shown for shown, _ in family["colors"]]}
                                  for family in PACKAGE_COLOR_FAMILIES])),
        # Fills لون اللوحه (field_49) on the work order; left empty it is copied from لون الغطاء
        (plate_color, f("plate_color", "لون اللوحه الاماميه، إن ينطبق", "select", options=PLATE_COLORS)),
        # The build details the work order's form in Daftra asks for
        (front_design, f("front_design", "تصميم القطعة الأمامية، إن ينطبق", "select", options=FRONT_DESIGNS)),
        (w_direction, f("w_direction", "اتجاه الدبليو، إن ينطبق", "select", options=W_DIRECTIONS)),
        # «بدون ظهر» unless another is chosen, so ظهر الكفر on the work order is never blank
        (cover_back, f("cover_back", "ظهر الكفر، إن ينطبق", "select", options=COVER_BACKS,
                       default=NO_COVER_BACK, blank_value=NO_COVER_BACK)),
        (design_version, f("design_version", "التصميم قديم أم جديد، إن ينطبق", "select", options=DESIGN_VERSIONS)),
        (base_color, f("base_color", "لون القاعدة، إن ينطبق", "select", options=BASE_COLORS)),
        # The package picked may start it off (PACKAGE_INSCRIPTIONS). While that one stays chosen it
        # carries its price in price_field and is named in work_field; the browser keeps them in step.
        (inscription, {**INSCRIPTION[0], "default_by_package": PACKAGE_INSCRIPTIONS,
                       "price_field": "inscription_price", "work_field": "installation_accessories"}),
        # beside: shown on the same line as that field, taking a third of it
        (inscription_price, money("inscription_price", "سعر الكتابة، شامل الضريبة (درهم)", charge=True,
                                  beside="inscription")),
        (manufacturing_notes, f("manufacturing_notes", "ملاحظات", "textarea",
                                placeholder="يتم اضافة تفاصيل الطلب بشكل كامل")),
        # What installing it involves, printed on the work order as ملحقات التركيب. The package picked
        # fills it in; the salesperson may add to it or empty it.
        (installation_accessories, f("installation_accessories", "ملحقات التركيب والأعمال المطلوبة", "textarea",
                                     default_by_package=INSTALLATION_WORK)),
        # A product with no fixed price: its price and invoice text, typed on its own line
        (item_price, ITEM_PRICE),
        (work_description, WORK_DESCRIPTION),
    )
    return switched(
        "تفاصيل الطلب",
        (order_lines, f("order_lines", "المنتجات والباقات", "order_lines", subtotal_field="subtotal_amount",
                        line_fields=lines)),
        note="إرسال الطلب يعني أن العميل وافق على التصميم واللون والكتابة.",
    )


def attachments(*, payment_proof, design_image, inscription_file):
    return switched(
        "المرفقات",
        (payment_proof, files("payment_proof", "إثبات الدفع")),
        (design_image, files("design_image", "صورة التصميم واللون المعتمدين")),
        (inscription_file, files("inscription_file", "صورة / ملف الكتابة، إن وجدت")),
    )


def installation(*, create_work_order, installation_days):
    return switched(
        "التركيب وأمر الشغل",
        (create_work_order, yes_no("create_work_order", "إنشاء أمر الشغل في دفترة")),
        # Any whole number of days (e.g. 15, 20, 17): the work order is due that many days after approval
        (installation_days, f("installation_days", "مدة التركيب (بالأيام)", "number", integer=True, min=1,
                              max=MAX_INSTALLATION_DAYS, placeholder="مثال: 15 أو 20", unit="يومًا")),
        note="عند الاعتماد يُنشأ أمر الشغل في دفترة والمدير المعتمِد مسؤولًا عنه، يبدأ يوم الاعتماد وينتهي بعد مدة التركيب، ويُربط بالفاتورة.",
    )


# ---------- the form ----------

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
        email=NEW_CLIENT(SHOW),
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
        inscription_price=REQUIRED_IF(HAS_INSCRIPTION),
        manufacturing_notes=SHOW,
        installation_accessories=SHOW,
        item_price=REQUIRED,
        work_description=REQUIRED,
    ),
    shared.amounts(
        subtotal_amount=SHOW,                       # the order lines' total
        total_amount=SHOW,                          # less the discount
        discount_label=REQUIRED_IF(DISCOUNTED),     # printed on the invoice under this name
        discount_amount=SHOW,
        discount_approved_by=REQUIRED_IF(DISCOUNTED),
        paid_amount=REQUIRED,
        remaining_amount=SHOW,
        remaining_due_date=REQUIRED_IF(HAS_REMAINDER),   # an instalment in Daftra
        must_pay=True,
    ),
    shared.payment(
        payment_method=REQUIRED,
        treasury=REQUIRED,
        payment_date=REQUIRED,
        payment_reference=REQUIRED,
        collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(
        payment_proof=REQUIRED,
        design_image=REQUIRED,
        inscription_file=SHOW,
    ),
    installation(
        create_work_order=REQUIRED,
        installation_days=REQUIRED_IF(WANTS_WORK_ORDER),
    ),
    shared.notes(notes=SHOW),
]
