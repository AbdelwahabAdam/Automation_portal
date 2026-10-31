"""The fields of طلب صيانة وتبديل, as sections (form_engine has the building blocks)."""

from ...modules.form_engine import (
    CASH_PAYMENT,
    NOTES,
    PAID,
    PAYMENT_METHODS,
    TREASURY_BY_METHOD,
    address,
    attachments,
    client,
    discount_fields,
    f,
    files,
    money,
    request_info,
    section,
)

# Choices only this form offers
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

SECTIONS = [
    request_info("تاريخ الطلب", invoiced=True),
    client(False, creates_client=True),
    address(),
    section(
        "تفاصيل الطلب",
        f("devices", "نوع الجهاز / البرادة (يمكن اختيار أكثر من جهاز)", "multiselect", True,
          options=MAINTENANCE_DEVICES, dropdown=True),
        f("service", "الخدمة", "select", True, options=MAINTENANCE_SERVICES, dropdown=True),
        # Only the catalog's maintenance items (products with a maintenance group). Every line is
        # priced on the line itself — MAINTENANCE_PRICES says where that starts — because what a
        # part or a service costs is settled per visit.
        f("order_lines", "إضافة بند", "order_lines", True, subtotal_field="subtotal_amount",
          items="maintenance_items", item_prices=MAINTENANCE_PRICES, line_fields=[
              money("item_price", "سعر الوحدة، شامل الضريبة (درهم)", True, line_price=True, column=True),
          ]),
        f("visit_date", "تاريخ الزيارة", "date", True),
    ),
    section(
        "قيمة الطلب",
        f("subtotal_amount", "قيمة البنود قبل الخصم، شامل الضريبة", "number", money=True, computed=[]),
        f("total_amount", "قيمة الطلب النهائية بعد الخصم، شامل الضريبة", "number", money=True,
          computed=["subtotal_amount", "discount_amount"], negative_message="قيمة الخصم أكبر من قيمة البنود"),
        *discount_fields(named=True, between=[
            # A maintenance visit is paid in full (or is free: 0)
            money("paid_amount", "المبلغ المدفوع فعليًا الآن", True, must_equal="total_amount",
                  must_equal_message="يجب دفع قيمة الطلب كاملة"),
        ]),
    ),
    section(
        "تفاصيل الدفعة",
        f("payment_method", "طريقة الدفع", "select", options=PAYMENT_METHODS, required_if=PAID),
        f("treasury", "الخزينة / الحساب المستلم في دفترة", "daftra_treasury",
          default_from={"field": "payment_method", "values": TREASURY_BY_METHOD}, required_if=PAID),
        f("payment_date", "تاريخ الدفع", "date", default="today", not_future=True, required_if=PAID),
        f("collector_name", "اسم المحصل، في حالة الدفع النقدي", "staff", required_if=CASH_PAYMENT),
    ),
    attachments(
        files("payment_proof", "إثبات الدفع، إن وُجدت دفعة", required_if=PAID),
        files("work_media", "صور / فيديو العطل أو الأعمال المنفذة، إن توفرت"),
    ),
    NOTES,
]
