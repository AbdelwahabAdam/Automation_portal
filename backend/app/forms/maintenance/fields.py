"""What طلب صيانة وتبديل asks: its sections, with one switch per field.

    HIDE  not asked      SHOW  asked, may be left empty      REQUIRED  must be filled
    REQUIRED_IF(when)    must be filled when `when` holds
"""

from ...modules.form_engine import (CASH_PAYMENT, DISCOUNTED, HIDE, NEW_CLIENT, PAID, REQUIRED, REQUIRED_IF, SHOW,
                                    DISCOUNT_AMOUNTS, DISCOUNT_LABELS, f, files, money, shared, switched,
                                    switched_fields)

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

# What a visit's parts and services cost, where the price is the same every time: the system head
# and its media, and the water connection. By Daftra product id, which is the same on every copy of
# the portal — our own catalog ids are not.
#
# The catalog's own prices are not used here. They are what each item sells for in a sale, and two
# of those readings differ: «Water Connection Service» costs 6 dirhams a metre when اعمال اضافية
# charges an extension by the metre, and 150 as a visit's service. Everything not named here is
# priced per visit — a filter, a spare part, a general service — so it is offered with no price and
# the salesperson types سعر الوحدة on the line.
MAINTENANCE_PRICES = {
    662: 725,    # MULTIPORT VALVE F56K — هيد السيستم F56K
    635: 150,    # GRAVEL SIZE 1-3 — ميديا حصى مقاس 1-3
    636: 150,    # GRAVEL SIZE 3-5 — ميديا حصى مقاس 3-5
    634: 150,    # SAND SIZE 04- 08 — ميديا رمل مقاس 04-08
    212: 150,    # Water Connection Service — خدمة تمديدات مياه
}


# ---------- this form's own sections ----------

def order_details(*, devices, service, order_lines, item_price, visit_date):
    """تفاصيل الطلب. Only the catalog's maintenance items (products with a maintenance group), each
    priced on its own line — MAINTENANCE_PRICES says where that starts — because what a part or a
    service costs is settled per visit."""
    return switched(
        "تفاصيل الطلب",
        (devices, f("devices", "نوع الجهاز / البرادة (يمكن اختيار أكثر من جهاز)", "multiselect",
                    options=MAINTENANCE_DEVICES, dropdown=True)),
        (service, f("service", "الخدمة", "select", options=MAINTENANCE_SERVICES, dropdown=True)),
        (order_lines, f("order_lines", "إضافة بند", "order_lines", subtotal_field="subtotal_amount",
                        items="maintenance_items", item_prices=MAINTENANCE_PRICES, line_fields=switched_fields(
                            (item_price, money("item_price", "سعر الوحدة، شامل الضريبة (درهم)",
                                               line_price=True, column=True)),
                        ))),
        (visit_date, f("visit_date", "تاريخ الزيارة", "date")),
    )


def amounts(*, subtotal_amount, total_amount, discount_label, discount_amount, paid_amount, discount_approved_by):
    """قيمة الطلب. A maintenance visit is paid in full, or is free (0)."""
    return switched(
        "قيمة الطلب",
        (subtotal_amount, f("subtotal_amount", "قيمة البنود قبل الخصم، شامل الضريبة", "number", money=True,
                            computed=[])),
        (total_amount, f("total_amount", "قيمة الطلب النهائية بعد الخصم، شامل الضريبة", "number", money=True,
                         computed=["subtotal_amount", "discount_amount"],
                         negative_message="قيمة الخصم أكبر من قيمة البنود")),
        # A named discount's name comes first: picking an initiative fills قيمة الخصم, beside it
        (discount_label, f("discount_label", "اسم الخصم كما يظهر في الفاتورة", max_length=100,
                           suggestions=DISCOUNT_LABELS, fills="discount_amount", fills_by_choice=DISCOUNT_AMOUNTS)),
        (discount_amount, money("discount_amount", "قيمة الخصم، إن وجد")),
        (paid_amount, money("paid_amount", "المبلغ المدفوع فعليًا الآن", must_equal="total_amount",
                            must_equal_message="يجب دفع قيمة الطلب كاملة")),
        (discount_approved_by, f("discount_approved_by", "اسم الشخص الذي اعتمد الخصم", "staff")),
    )


def attachments(*, payment_proof, work_media):
    return switched(
        "المرفقات",
        (payment_proof, files("payment_proof", "إثبات الدفع، إن وُجدت دفعة")),
        (work_media, files("work_media", "صور / فيديو العطل أو الأعمال المنفذة، إن توفرت")),
    )


# ---------- the form ----------

SECTIONS = [
    shared.request_info(
        request_date=REQUIRED,
        employee_name=SHOW,
        order_source=REQUIRED,
        source=HIDE,
        labels={"request_date": "تاريخ الطلب"},
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
        devices=REQUIRED,
        service=REQUIRED,
        order_lines=REQUIRED,
        item_price=REQUIRED,
        visit_date=REQUIRED,
    ),
    amounts(
        subtotal_amount=SHOW,
        total_amount=SHOW,
        discount_label=REQUIRED_IF(DISCOUNTED),
        discount_amount=SHOW,
        paid_amount=REQUIRED,
        discount_approved_by=REQUIRED_IF(DISCOUNTED),
    ),
    shared.payment(
        payment_method=REQUIRED_IF(PAID),
        treasury=REQUIRED_IF(PAID),
        payment_date=REQUIRED_IF(PAID),
        payment_reference=HIDE,
        collector_name=REQUIRED_IF(CASH_PAYMENT),
    ),
    attachments(
        payment_proof=REQUIRED_IF(PAID),
        work_media=SHOW,
    ),
    shared.notes(notes=SHOW),
]
