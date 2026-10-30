"""The choices the forms offer, and the rules that follow from them (e.g. a package's colours)."""

from ...core.text import squash

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
SOURCES = ["ماركتنج", "عميل شركة", "عميل جديد", "عميل سابق", "مكتب", "الموقع", "أخرى"]
COLORS = ["أبيض", "أسود", "ذهبي", "أخرى"]
# A new client's نوع العميل and الجنس, with what Daftra stores for each (Client.type, Client.gender)
CUSTOMER_TYPES = {"شركة": 3, "فرد": 2}
GENDERS = {"ذكر": 1, "أنثى": 2}

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


# What the installation of a package involves, as the technicians read it on the work order
# (ملحقات التركيب). The salesperson is given the text of the package they picked and may change it
# or empty it; a package no family matches starts empty. Matched on the words of the package's
# name, like PACKAGE_COLOR_FAMILIES above, so a new colour or size of a known cooler needs no edit
# here. The three texts are the ones staff write by hand today.
INSTALLATION_WORK = [
    # A food cooler takes no water: electricity, the sensor, the lighting and a tiled base
    {"match": ["حفظ الطعام"], "exclude": [], "text":
        "تمديد كهرباء كامل للبرادة • سينسور إضاءة تلقائي. • إضاءة جانبية + بروفايل ليد * عمل قاعده سراميك"},
    # Stainless, and the six-tap cooler: the filter and whatever extensions the place needs
    {"match": ["ستانلس", "6 صنابير"], "exclude": [], "text":
        "فلتر 3 مراحل + عمل التمديدات اللازمه"},
    # Every نبع المزن and سقيا الخير water cooler, plain or مدمجة
    {"match": ["نبع المزن", "سقيا الخير"], "exclude": ["حفظ الطعام", "ستانلس"], "text":
        "تمديد مياه وكهرباء كامل للبرادة • تركيب فلتر 3 مراحل * مع تركيب صندوق الفلتر • "
        "سينسور إضاءة تلقائي. • إضاءة جانبية + بروفايل ليد *"},
]


def installation_work(package_name: str) -> str:
    """What installing this package involves, or '' when nothing is written for it.
    frontend/src/modules/requests/validation.js packageDefault() mirrors this."""
    name = squash(package_name)
    for family in INSTALLATION_WORK:
        if any(word in name for word in family["match"]) and not any(word in name for word in family["exclude"]):
            return family["text"]
    return ""


MAX_PACKAGE_QUANTITY = 99



def package_quantity(line: dict) -> int:
    """How many of the package this line was picked from: 1 for a product picked on its own."""
    try:
        value = int(float(str((line.get("details") or {}).get("package_quantity") or 1)))
    except ValueError:
        value = 1
    return value if line.get("group_id") and 0 < value <= MAX_PACKAGE_QUANTITY else 1
