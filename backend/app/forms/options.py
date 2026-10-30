"""The choices the forms offer, and the rules that follow from them (e.g. a package's colours)."""

from ..text import squash

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
# A new client's نوع العميل and الجنس, with what Daftra stores for each (Client.type, Client.gender)
CUSTOMER_TYPES = {"شركة": 3, "فرد": 2}
GENDERS = {"ذكر": 1, "أنثى": 2}

# The renewal price a طلب تجديد عقد الصيانة السنوي starts from; the salesperson can change it
RENEWAL_PRICE = 1680
# What an inscription field holds when there is no inscription, so nothing is charged for it
NO_INSCRIPTION = ["لا يوجد", "لايوجد", "لا توجد", "لاتوجد"]
# Names already used for discounts on our Daftra invoices, offered as suggestions
DISCOUNT_LABELS = ["مبادرة دعم نبع المزن", "مبادرة دعم سقيا الخير", "مبادرة لك ان تشارك", "خصم من قبل الإدارة"]
# What an initiative takes off, filled into قيمة الخصم when its name is picked and changeable after.
# A name that is not an initiative («خصم من قبل الإدارة») has no amount of its own, so nothing is filled in.
DISCOUNT_AMOUNTS = {"مبادرة دعم نبع المزن": 1275, "مبادرة دعم سقيا الخير": 1750, "مبادرة لك ان تشارك": 1150}
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
    name = squash(package_name)
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
# اعمال اضافية (قسم الفنيات) offers these services and nothing else. They are named by their Daftra
# product id, which is the same on every copy of the portal — our own catalog ids are not.
# 194 «service» is «أخرى»: the work is described and priced on the line, and the invoice carries it
# as a service line, exactly as الكتابة المطلوبة does.
OTHER_WORK_DAFTRA_ID = 194
# What the form calls each of them, in the order it offers them. The names are the portal's own:
# the invoice carries the product's name as Daftra holds it (Water Connection Service and the rest),
# since that is what the accounts are kept in.
TECH_SERVICE_LABELS = {
    212: "تمديد المياة",                  # Water Connection Service — «Water extension»
    418: "تمديد الكهرباء",                # Electricity Connection Service — «Electricity extension»
    433: "اعمال باسكو",                   # interlocking paving Removel $ Breaking Service (code 2016)
    OTHER_WORK_DAFTRA_ID: "أخرى",         # the catalog's general «service», described on the line
}
TECH_SERVICE_DAFTRA_IDS = list(TECH_SERVICE_LABELS)
# How many days an installation takes, i.e. the work order's delivery date after its start
# The longest مدة التركيب a work order can be given, in days
MAX_INSTALLATION_DAYS = 365
