"""The choices the forms offer, and the rules that follow from them (e.g. a package's colours)."""

from ...core.text import squash

YES_NO = ["نعم", "لا"]
CASH = "نقدًا"
# العين is offered as one of its own, though Daftra's own addresses keep it inside أبوظبي:
# the work there is a department of its own, and the تصنيفات of منطقة العين say العين.
EMIRATES = ["أبوظبي", "العين", "دبي", "الشارقة", "عجمان", "أم القيوين", "رأس الخيمة", "الفجيرة"]
PAYMENT_METHODS = ["تحويل بنكي", CASH, "ماكينة POS", "تابي", "تمارا", "طلب من الموقع"]
SOURCES = ["ماركتنج", "عميل شركة", "عميل جديد", "عميل سابق", "مكتب", "الموقع", "أخرى"]
COLORS = ["أبيض", "أسود", "ذهبي", "أخرى"]
# A client's نوع العميل and الجنس, with what Daftra stores for each (Client.type, Client.gender)
CUSTOMER_TYPES = {"فرد": 2, "تجاري": 3}
GENDERS = {"ذكر": 1, "أنثى": 2}
# Daftra's code for every نوع العميل a request can hold: «تجاري» was «شركة» on requests made before
CUSTOMER_TYPE_CODES = {**CUSTOMER_TYPES, "شركة": 3}

# What an inscription field holds when there is no inscription, so nothing is charged for it
NO_INSCRIPTION = ["لا يوجد", "لايوجد", "لا توجد", "لاتوجد"]
# Names already used for discounts on our Daftra invoices, offered as suggestions
DISCOUNT_LABELS = ["مبادرة دعم نبع المزن", "مبادرة دعم سقيا الخير", "مبادرة لك ان تشارك", "خصم من قبل الإدارة"]
# What an initiative takes off, filled into قيمة الخصم when its name is picked and changeable after.
# A name that is not an initiative («خصم من قبل الإدارة») has no amount of its own, so nothing is filled in.
DISCOUNT_AMOUNTS = {"مبادرة دعم نبع المزن": 1275, "مبادرة دعم سقيا الخير": 1750, "مبادرة لك ان تشارك": 1150}
# The treasury a payment usually goes into in Daftra, by payment method; the salesperson can change it
TREASURY_BY_METHOD = dict(zip(PAYMENT_METHODS, [13, 9, 16, 7, 8, 12]))

# The colours a plate is written in on the work order, and what لون الغطاء offers for a package
# with no list of its own. Written as the work order carries them, so nothing has to be translated.
PLATE_COLORS = ["اللون الابيض", "اللون الاسود", "اللون الدهبي", "اللون الخشبي",
                "اللون العيناوي", "اللون الازرق"]

# Conditions used with required_if
PAID = {"field": "paid_amount", "gt": 0}
DISCOUNTED = {"field": "discount_amount", "gt": 0}
CASH_PAYMENT = {"field": "payment_method", "equals": CASH}
# A package's cover colours (لون الغطاء) depend on the package. Each family: the words its package names
# contain (and must not contain), and its colours as (shown in the form, written on the Daftra work order
# as «الألوان المتاحة», exactly as staff write it there). The first family that matches wins; a package
# that matches none offers the field's own default_colors instead (PLATE_COLORS).
PACKAGE_COLOR_FAMILIES = [
    # حفظ الطعام (FLP-023/024): the six plain colours every package without a list of its own gets,
    # and «اسود في بني», which these covers alone come in. First, so no cooler family above takes
    # them by the «سقيا الخير»/«نبع المزن» in their names. Written as "": Daftra's list has no entry
    # for these covers, and an empty one leaves the work order to say it in words, as it did before.
    {"match": ["حفظ الطعام"], "exclude": [], "colors": [
        *((color, "") for color in PLATE_COLORS),
        ("اسود في بني", ""),
    ]},
    # «مدمج» without its last letter: the catalogue was imported as «مدمجة» (jobs/import_catalog.py) and
    # the live names are written «مدمجه», so the word in full matched neither one or the other and the
    # combined packages fell through to the plain سقيا الخير colours below.
    {"match": ["سقيا الخير مدمج"], "exclude": [], "colors": [
        # The trailing space is the Daftra list's own, and an entry must match it to the letter
        ("الابيض", "سقيا الخير مدمجه - اللون الابيض "),
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


# ---------- which fields a package asks for ----------
# The line fields each family of packages shows. A package no profile matches keeps every field the
# form has, as it always did, so nothing changes for the rest of the catalogue.
#   match:   the package shows this profile when its name carries any of these words
#   needs:   …and all of these (نبع المزن المدمجة alone asks whether the design is old or new)
#   exclude: …and none of these
#   fields:  the line's own fields it shows. الكمية and the open-price pair are structural and
#            always kept, and a field shown «beside» a kept one goes with it (سعر الكتابة).
#   labels:  what a field is called on this package («لون الباب» rather than «لون البرادة»)
#   options: a shorter list of choices for one of its selects
# Matching is on the name, as PACKAGE_COLOR_FAMILIES is: the browser has the name on every line and
# resolves the same profile with the same words (validation.js packageProfile).
_COOLER_FIELDS = ["cooler_color", "cover_color", "plate_color", "base_color", "front_design",
                  "w_direction", "cover_back", "design_version", "inscription",
                  "manufacturing_notes", "installation_accessories"]
_WITHOUT_DESIGN_VERSION = [name for name in _COOLER_FIELDS if name != "design_version"]
_SUQYA_FIELDS = ["cooler_color", "cover_color", "plate_color", "base_color", "cover_back",
                 "inscription", "manufacturing_notes", "installation_accessories"]

PACKAGE_PROFILES = [
    # FLP-035 فلتر دش Future Life: one colour, and only two of them. The choices keep the catalogue's
    # own spelling (COLORS), not «اسود»/«ابيض»: work_order.COLOR_TEXT turns these into the words
    # Daftra's own list holds, and a colour spelled otherwise is emptied on the work order.
    {"match": ["فلتر دش"], "fields": ["cooler_color"],
     "labels": {"cooler_color": "اللون"},
     "options": {"cooler_color": ["أبيض", "أسود"]}},
    # FLP-036..039, the doors (جرار and مفصلي). «لوح خلفي/كلادينج ثابت» (FLP-040..042) carry no door,
    # so they match nothing here and keep their fields.
    {"match": ["باب خلفي"], "fields": ["cooler_color", "w_direction", "manufacturing_notes"],
     "labels": {"cooler_color": "لون الباب"}},
    # نبع المزن: the combined ones are the only packages asked whether the design is old or new.
    # «مدمج» without its last letter, as the catalogue writes both مدمجه and مدمجة.
    {"match": ["نبع المزن"], "needs": ["مدمج"], "fields": _COOLER_FIELDS},
    {"match": ["نبع المزن"], "fields": _WITHOUT_DESIGN_VERSION},
    # Not the stainless ones, which are «other packages» and keep every field. The live catalogue
    # names them «باقة برادة ستانلس ستيل», but they were imported as «… سقيا الخير ستانلس ستيل», and
    # the colour families leave them out for the same reason.
    {"match": ["سقيا الخير"], "exclude": ["ستانلس"], "fields": _SUQYA_FIELDS},
]


def package_profile(package_name: str, profiles: list[dict] | None = None) -> dict | None:
    """The first profile the package's name matches, or None when it matches none — which means
    every field, as before. Mirrored in frontend/src/modules/requests/validation.js."""
    name = squash(package_name)
    for profile in PACKAGE_PROFILES if profiles is None else profiles:
        if (any(word in name for word in profile["match"])
                and all(word in name for word in profile.get("needs", ()))
                and not any(word in name for word in profile.get("exclude", ()))):
            return profile
    return None


def package_fields(line_fields: list[dict], package_name: str, profiles: list[dict] | None = None) -> list[dict]:
    """`line_fields` as this package asks for them: the ones its profile lists, relabelled and with
    its own choices where it gives them. A package matching no profile keeps them all."""
    profile = package_profile(package_name, profiles)
    if profile is None:
        return line_fields
    keep = set(profile["fields"])
    keep |= {spec["name"] for spec in line_fields if spec.get("beside") in keep}
    labels, options = profile.get("labels", {}), profile.get("options", {})
    kept = []
    for spec in line_fields:
        # الكمية and the open-price pair are structural: every package has them
        if not (spec["name"] in keep or spec.get("package_only") or spec.get("open_price_only")):
            continue
        changes = {}
        if spec["name"] in labels:
            changes["label"] = labels[spec["name"]]
        if spec["name"] in options:
            changes["options"] = list(options[spec["name"]])
        kept.append({**spec, **changes} if changes else spec)
    return kept


def package_colors(package_name: str) -> list[tuple[str, str]]:
    """The colours a package's name allows, as (shown, as written on the work order); [] for none.

    [] does not mean the field is hidden: a «package_color» field with default_colors offers those
    instead (لون الغطاء is asked for on every package). The browser mirrors this in
    frontend/src/modules/requests/validation.js packageColors().
    """
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

# The inscription a package starts with, matched like the two lists above: its wording as the
# catalogue saves it, its price, and how ملحقات التركيب names it while it is the one chosen.
PACKAGE_INSCRIPTIONS = [
    # No «work»: the verse is not written into ملحقات التركيب. That box is what the floor installs; the
    # verse already has its own place, الكتابة المطلوبة, and its own field on the work order (field_47).
    {"match": ["سقيا الخير"], "exclude": [], "text": "وجعلنا من الماء كل شيئ حي", "price": "0"},
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
