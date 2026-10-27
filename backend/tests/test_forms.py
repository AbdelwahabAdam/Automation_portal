"""The form definitions and their validation (app.forms), without the database."""

from datetime import date, timedelta

from app import forms
from app.forms import FORM_TYPES, form_fields, package_colors, package_quantity, sanitize_draft, validate_submission
from app.text import uae_today

PACKAGE = "باقة برادة سقيا الخير - 3 صنابير - أسود"
PRODUCTS = {
    "1": {"id": 1, "name": "WATER COOLER BLACK 3 T", "price": 1000, "maintenance_group": None},
    "2": {"id": 2, "name": "exchange contract", "price": 1200, "maintenance_group": None},
    "3": {"id": 3, "name": "RO .PP 10", "price": 50, "maintenance_group": "الفلاتر"},
}
PACKAGE_PRICES = {("10", "1"): 2000.0, ("10", "2"): 800.0}
LISTS = {"daftra_order_source": {16: "Sales-جديد"}, "daftra_treasury": {13: "ADIB NEW CURRENT", 9: "خزينه المكتب"},
         "daftra_client_category": {5: "العين العامره"}}
# What the portal calls today is the UAE's day, which is not the machine's when it runs behind UTC+4
TODAY = uae_today().isoformat()


def package_lines(quantity=2, **details):
    shared = {"package_quantity": str(quantity), "cooler_color": "أسود", "cover_color": "الاسود مقاس طبيعي",
              "inscription": "بسم الله", "inscription_price": "300", **details}
    return [
        {"product_id": "1", "name": "WATER COOLER BLACK 3 T", "quantity": quantity, "base_quantity": 1, "group_id": "g1",
         "group_name": PACKAGE, "package_id": 10, "unit_price": 1, "details": dict(shared)},
        {"product_id": "2", "name": "exchange contract", "quantity": quantity, "base_quantity": 1, "group_id": "g1",
         "group_name": PACKAGE, "package_id": 10, "unit_price": 1, "details": dict(shared)},
    ]


def new_sale(**overrides):
    data = {
        "request_date": TODAY, "order_source": "16", "phone": "0501234567", "customer_name": "عميل تجريبي",
        "customer_type": "فرد", "gender": "ذكر",
        "category": "5", "area": "منطقة العين", "emirate": "أبوظبي", "street": "شارع 1", "house": "فيلا 2",
        "location_url": "https://www.google.com/maps?q=24.178700,55.604510", "coordinates": "24.178700, 55.604510",
        "order_lines": package_lines(), "discount_amount": "200", "discount_approved_by": "Manager One",
        "discount_label": "مبادرة لك ان تشارك", "paid_amount": "1000", "remaining_due_date": TODAY,
        "payment_method": "تحويل بنكي", "treasury": "13", "payment_date": TODAY, "payment_reference": "TRX-1",
        "create_work_order": "نعم", "installation_days": "20",
    }
    data.update(overrides)
    return data


def validate(form_type, data, files=None):
    return validate_submission(form_type, data, files or {}, "Sales One", PRODUCTS, PACKAGE_PRICES, LISTS)


FILES = {"payment_proof": 1, "design_image": 1}


def test_new_sale_works_out_prices_and_totals_on_the_server():
    clean, errors = validate("new_sale", new_sale(), FILES)
    assert errors == {}
    # The browser's unit_price (1) is ignored: each product's price inside its package is used
    assert [line["unit_price"] for line in clean["order_lines"]] == [2000.0, 800.0]
    # 2 packages: (2000 + 800) x 2, plus the inscription (300) once per package, x 2
    assert clean["subtotal_amount"] == 6200
    assert clean["total_amount"] == 6000
    assert clean["remaining_amount"] == 5000
    assert clean["employee_name"] == "Sales One"
    assert clean["order_source_name"] == "Sales-جديد"
    assert clean["treasury_name"] == "ADIB NEW CURRENT"
    assert clean["category_name"] == "العين العامره"
    assert clean["paid_amount"] == 1000.0


def test_new_sale_required_and_conditional_fields():
    data = new_sale(discount_approved_by="", discount_label="", remaining_due_date="", installation_days="")
    _, errors = validate("new_sale", data, {})
    assert errors["payment_proof"] == "أرفق ملفًا واحدًا على الأقل"
    assert errors["design_image"] == "أرفق ملفًا واحدًا على الأقل"
    # Required because a discount was given, something is left to pay, and a work order is wanted
    for name in ("discount_approved_by", "discount_label", "remaining_due_date", "installation_days"):
        assert errors[name] == "مطلوب", name


def test_new_sale_without_work_order_needs_no_installation_days():
    _, errors = validate("new_sale", new_sale(create_work_order="لا", installation_days=""), FILES)
    assert "installation_days" not in errors


def test_new_sale_work_order_starts_unanswered_and_must_be_chosen():
    spec = next(s for s in form_fields("new_sale") if s["name"] == "create_work_order")
    assert "default" not in spec
    _, errors = validate("new_sale", new_sale(create_work_order="", installation_days=""), FILES)
    assert errors["create_work_order"] == "مطلوب"
    assert "installation_days" not in errors


def test_new_sale_must_pay_something():
    _, errors = validate("new_sale", new_sale(paid_amount="0"), FILES)
    assert errors["paid_amount"] == "يجب أن يكون أكبر من صفر"


def test_discount_larger_than_the_order_is_refused():
    _, errors = validate("new_sale", new_sale(discount_amount="9999"), FILES)
    assert errors["total_amount"] == "قيمة الخصم أكبر من قيمة الطلب قبل الخصم"


def test_line_errors_are_reported_per_line():
    lines = package_lines(cooler_color="", inscription_price="")
    _, errors = validate("new_sale", new_sale(order_lines=lines), FILES)
    assert errors["order_lines"]["lines"]["0"] == {"cooler_color": "مطلوب", "inscription_price": "مطلوب"}


def test_no_inscription_needs_no_price_and_charges_nothing():
    clean, errors = validate("new_sale", new_sale(order_lines=package_lines(inscription="لا يوجد", inscription_price="")), FILES)
    assert "order_lines" not in errors
    assert clean["subtotal_amount"] == 5600


def test_an_inscription_left_empty_is_saved_as_there_being_none():
    """It is not asked for any more: left empty it means «لا يوجد», and nothing is charged for it."""
    clean, errors = validate("new_sale", new_sale(order_lines=package_lines(inscription="", inscription_price="")), FILES)
    assert errors == {}
    assert [line["details"]["inscription"] for line in clean["order_lines"]] == ["لا يوجد", "لا يوجد"]
    assert clean["subtotal_amount"] == 5600


def test_an_empty_inscription_on_a_form_that_asks_it_once_is_saved_the_same_way():
    # طلب عرض سعر asks for it as a field of its own, not per line; the rest of the form is beside the point here
    clean, errors = validate("quotation", {"inscription": ""})
    assert "inscription" not in errors
    assert clean["inscription"] == "لا يوجد"


def test_cover_colour_must_be_one_of_the_package_family():
    _, errors = validate("new_sale", new_sale(order_lines=package_lines(cover_color="بنفسجي")), FILES)
    assert errors["order_lines"]["lines"]["0"]["cover_color"] == "اختر من القائمة"


def test_unknown_products_are_dropped_and_an_empty_order_refused():
    lines = [{"product_id": "999", "name": "gone", "quantity": 1, "details": {}}]
    _, errors = validate("new_sale", new_sale(order_lines=lines), FILES)
    assert errors["order_lines"] == "اختر منتجًا أو باقة واحدة على الأقل"


def test_maintenance_only_takes_maintenance_items_and_must_be_paid_in_full():
    data = {
        "request_date": TODAY, "order_source": "16", "phone": "0501234567", "customer_name": "عميل",
        "category": "5", "area": "منطقة العين", "emirate": "أبوظبي",
        "location_url": "https://www.google.com/maps?q=24.100000,55.600000", "coordinates": "24.100000, 55.600000",
        "devices": ["فلتر RO VIB", "not a device"], "service": "تبديل فلاتر", "visit_date": TODAY,
        "order_lines": [
            {"product_id": "3", "name": "RO .PP 10", "quantity": 2, "details": {}},
            # Not a maintenance item: dropped whatever the browser sends
            {"product_id": "1", "name": "WATER COOLER BLACK 3 T", "quantity": 1, "details": {}},
        ],
        "paid_amount": "50", "payment_method": "تحويل بنكي", "treasury": "13", "payment_date": TODAY,
    }
    clean, errors = validate("maintenance", data, {"payment_proof": 1})
    assert [line["product_id"] for line in clean["order_lines"]] == ["3"]
    assert clean["devices"] == ["فلتر RO VIB"]
    assert clean["subtotal_amount"] == 100
    assert errors == {"paid_amount": "يجب دفع قيمة الطلب كاملة"}


def test_field_types_are_checked():
    tomorrow = (uae_today() + timedelta(days=1)).isoformat()
    data = new_sale(phone="12345", request_date=tomorrow, client_code="12a", treasury="77", emirate="باريس")
    _, errors = validate("new_sale", data, FILES)
    assert errors["phone"] == "أدخل رقم هاتف إماراتي صحيح"
    assert errors["request_date"] == "التاريخ لا يمكن أن يكون في المستقبل"
    assert errors["client_code"] == "أرقام فقط، حتى 6 خانات"
    assert errors["treasury"] == "اختر من القائمة"
    assert errors["emirate"] == "اختر من القائمة"


def test_arabic_digits_and_separators_are_read():
    clean, errors = validate("new_sale", new_sale(phone="٠٥٠ ١٢٣ ٤٥٦٧", paid_amount="١,٠٠٠"), FILES)
    assert "phone" not in errors and clean["phone"] == "0501234567"
    assert clean["paid_amount"] == 1000


def test_a_daftra_list_that_could_not_be_loaded_accepts_the_id():
    clean, errors = validate_submission("new_sale", new_sale(order_source="55"), FILES, "x", PRODUCTS, PACKAGE_PRICES,
                                        {k: v for k, v in LISTS.items() if k != "daftra_order_source"})
    assert "order_source" not in errors and clean["order_source"] == 55


def test_balance_payment_requires_the_invoice_and_a_positive_amount():
    _, errors = validate("balance_payment", {"phone": "0501234567", "client_code": "4100", "customer_name": "x",
                                             "paid_amount": "0"})
    assert errors["invoice"] == "مطلوب"
    assert errors["paid_amount"] == "يجب أن يكون أكبر من صفر"


def test_contract_renewal_total_follows_the_typed_price():
    data = {"request_date": TODAY, "order_source": "16", "phone": "0501234567", "customer_name": "x", "category": "5",
            "area": "منطقة العين", "emirate": "أبوظبي", "cooler_type": "سقيا",
            "location_url": "https://www.google.com/maps?q=1.100000,2.200000", "coordinates": "1.100000, 2.200000",
            "subtotal_amount": "1680", "discount_amount": "80", "discount_approved_by": "M", "discount_label": "خصم",
            "paid_amount": "1600", "payment_method": "تحويل بنكي", "treasury": "13", "payment_date": TODAY,
            "payment_reference": "T"}
    clean, errors = validate("contract_renewal", data, {"payment_proof": 1})
    assert errors == {}
    assert clean["total_amount"] == 1600 and clean["remaining_amount"] == 0


def test_package_helpers():
    assert package_colors("باقة سقيا الخير ستانلس")[:1] == []
    assert package_colors("نبع المزن مدمجة")[0][0] == "البني والأسود"
    assert package_colors("سقيا الخير مدمجة - ذهبي")[0][0] == "الابيض"
    assert package_quantity({"group_id": "g", "details": {"package_quantity": "3"}}) == 3
    assert package_quantity({"group_id": None, "details": {"package_quantity": "3"}}) == 1
    assert package_quantity({"group_id": "g", "details": {"package_quantity": "500"}}) == 1
    assert package_quantity({"group_id": "g", "details": {"package_quantity": "abc"}}) == 1


def test_drafts_keep_what_was_typed_without_validating():
    draft = sanitize_draft("new_sale", {"phone": "bad phone", "paid_amount": "abc", "unknown": "dropped",
                                        "order_source": "16", "order_source_name": "Sales-جديد",
                                        "order_lines": package_lines() + ["junk", {"name": "no product"}]})
    assert draft["phone"] == "bad phone" and draft["paid_amount"] == "abc"
    assert "unknown" not in draft
    assert draft["order_source_name"] == "Sales-جديد"
    assert len(draft["order_lines"]) == 2
    assert draft["order_lines"][0]["details"]["package_quantity"] == "2"


def test_every_form_definition_is_consistent():
    for key, definition in FORM_TYPES.items():
        names = [spec["name"] for spec in form_fields(key)]
        assert len(names) == len(set(names)), f"{key} repeats a field name"
        for spec in form_fields(key):
            if spec["type"] in ("select", "multiselect"):
                assert spec["options"], f"{key}.{spec['name']} has no options"
            for condition in [spec.get("required_if")] if spec.get("required_if") else []:
                assert condition["field"] in names, f"{key}.{spec['name']} depends on an unknown field"
            for operand in spec.get("computed", []):
                assert operand in names, f"{key}.{spec['name']} is computed from an unknown field"
    assert forms.VISIBLE_FORM_TYPES <= set(FORM_TYPES)


def test_numbers_that_are_not_amounts_are_refused():
    for typed in ("inf", "-Infinity", "nan", "1e400"):
        _, errors = validate("new_sale", new_sale(paid_amount=typed), FILES)
        assert errors["paid_amount"] == "أدخل رقمًا صحيحًا", typed


def test_malformed_order_lines_do_not_break_validation_or_drafts():
    lines = ["text", 5, None, {"product_id": "1", "quantity": 1, "details": "not a dict", "unit_price": float("inf")}]
    clean, errors = validate("new_sale", new_sale(order_lines=lines), FILES)
    assert len(clean["order_lines"]) == 1
    draft = sanitize_draft("new_sale", {"order_lines": lines})
    assert draft["order_lines"][0]["details"] == {} and draft["order_lines"][0]["unit_price"] is None


def test_dates_are_checked_against_the_uae_day(monkeypatch):
    monkeypatch.setattr("app.forms.validation.uae_today", lambda: date(2026, 10, 21))
    _, errors = validate("new_sale", new_sale(request_date="2026-10-21", payment_date="2026-10-21",
                                              remaining_due_date="2026-10-21"), FILES)
    assert "request_date" not in errors
    _, errors = validate("new_sale", new_sale(request_date="2026-10-22"), FILES)
    assert errors["request_date"] == "التاريخ لا يمكن أن يكون في المستقبل"


def test_text_helpers():
    from app.text import day_month_year, digits, squash

    assert day_month_year("2026-10-19") == "19/10/2026"
    assert day_month_year("2026-10-19 10:30:00") == "19/10/2026"
    assert day_month_year("soon") == "soon"
    assert digits("٠٥٠-١٢٣ 4567") == "0501234567"
    assert squash("  a \n  b ") == "a b"


def test_every_amount_field_is_marked_as_money():
    """The form and the request's page print a money field with «درهم»; a count must not be."""
    for key in FORM_TYPES:
        for spec in form_fields(key):
            if spec["type"] != "number":
                continue
            looks_like_money = any(word in spec["name"] for word in ("amount", "price", "paid", "refund", "total", "value"))
            assert spec.get("money", False) == looks_like_money, f"{key}.{spec['name']}"


def test_the_area_keeps_the_neighbourhood_daftra_holds():
    """المنطقة is not a list to pick from: Daftra's own addresses hold a neighbourhood, and only
    28 of the 3,931 we imported hold one of the regions the form suggests."""
    clean, errors = validate("new_sale", new_sale(area="الخوانيج 2"), FILES)
    assert "area" not in errors
    assert clean["area"] == "الخوانيج 2"


def test_the_coordinates_are_the_point_in_the_location_whatever_is_sent():
    """الإحداثيات are the pin's own position. The field is read-only in the form, which stops a
    person typing in it but not a browser, so the server takes them from the location itself."""
    data = new_sale(location_url="https://www.google.com/maps?q=25.200000,55.270000",
                    coordinates="1.000000, 2.000000")
    clean, errors = validate("new_sale", data, FILES)
    assert errors == {}
    assert clean["coordinates"] == "25.200000, 55.270000"


def test_a_request_needs_a_location():
    _, errors = validate("new_sale", new_sale(location_url="", coordinates=""), FILES)
    assert errors["location_url"] == "مطلوب"


def test_a_location_that_is_not_a_map_link_is_refused():
    _, errors = validate("new_sale", new_sale(location_url="24.1787, 55.6045"), FILES)
    assert errors["location_url"] == "اختر الموقع على الخريطة"


def test_coordinates_typed_by_hand_are_kept_when_the_location_has_no_point():
    """A link shared from a phone's own position holds the place's name and not where it is, so
    الإحداثيات are filled in by hand instead — and still required."""
    gps = "https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic"
    clean, errors = validate("new_sale", new_sale(location_url=gps, coordinates="24.500000, 55.900000"), FILES)
    assert errors == {}
    assert clean["coordinates"] == "24.500000, 55.900000"


def test_a_location_with_no_point_still_needs_coordinates():
    gps = "https://maps.app.goo.gl/GQHpiS558z2DLsuG7?g_st=ic"
    _, errors = validate("new_sale", new_sale(location_url=gps, coordinates=""), FILES)
    assert errors["coordinates"] == "مطلوب"


def test_a_phone_is_kept_in_the_one_form_the_client_list_uses():
    """However it was written, it is stored as 0501234567 — what clients and Daftra are searched by."""
    for written in ["+971 50 123 4567", "00971501234567", "971501234567", "050 123 4567", "٠٥٠١٢٣٤٥٦٧"]:
        clean, errors = validate("new_sale", new_sale(phone=written), FILES)
        assert errors == {}, written
        assert clean["phone"] == "0501234567", written


def test_only_a_real_uae_number_is_accepted():
    # 59 is no operator's, 01 no emirate's, and the length has to be right
    for no in ["0591234567", "0101234567", "05012345", "05012345678", "+44 20 7946 0000", "12345"]:
        _, errors = validate("new_sale", new_sale(phone=no), FILES)
        assert errors.get("phone") == "أدخل رقم هاتف إماراتي صحيح", no


def test_a_landline_is_a_number_too():
    for written in ["04 123 4567", "+971 3 765 4321"]:
        clean, errors = validate("new_sale", new_sale(phone=written), FILES)
        assert errors == {}, written


def new_client(data, **overrides):
    return validate_submission("new_sale", {**data, **overrides}, FILES, "Sales One", PRODUCTS, PACKAGE_PRICES, LISTS,
                               new_client=True)


def test_a_new_client_needs_a_type_and_gender_and_may_give_an_email():
    spec = {s["name"]: s for s in form_fields("new_sale")}
    assert spec["customer_type"]["options"] == ["شركة", "فرد"]
    assert spec["gender"]["options"] == ["ذكر", "أنثى"]
    _, errors = new_client(new_sale(), customer_type="", gender="")
    assert errors["customer_type"] == "مطلوب" and errors["gender"] == "مطلوب"
    # Email is optional; one that is given must look like an email
    clean, errors = new_client(new_sale(), email="")
    assert not errors and "email" not in clean
    for bad in ("name@", "name example.com", "name@example", "@example.com"):
        _, errors = new_client(new_sale(), email=bad)
        assert errors["email"].startswith("أدخل بريدًا إلكترونيًا صحيحًا"), bad
    clean, errors = new_client(new_sale(), customer_type="شركة", gender="أنثى", email=" Office@Example.COM ")
    assert not errors and (clean["customer_type"], clean["gender"], clean["email"]) == ("شركة", "أنثى", "office@example.com")
    _, errors = new_client(new_sale(), customer_type="Business")
    assert errors["customer_type"] == "اختر من القائمة"


def test_an_existing_client_is_not_asked_for_type_gender_or_email():
    # Daftra already has them; anything sent is left out rather than written over theirs
    clean, errors = validate("new_sale", new_sale(customer_type="", gender="", email="not-an-email"), FILES)
    assert not any(name in errors or name in clean for name in ("customer_type", "gender", "email"))


def test_only_forms_that_create_a_daftra_client_ask_for_type_gender_and_email():
    # Only the forms whose approval creates a client in Daftra ask; a renewal is for a client Daftra has
    asking = {key for key in FORM_TYPES if {"customer_type", "gender", "email"} <= {s["name"] for s in form_fields(key)}}
    assert asking == {"new_sale", "maintenance"}


def test_installation_days_is_any_whole_number_of_days():
    for typed, kept in (("15", 15), ("17", 17), ("١٢", 12), ("365", 365)):
        clean, errors = validate("new_sale", new_sale(installation_days=typed), FILES)
        assert "installation_days" not in errors and clean["installation_days"] == kept, typed
    for typed, message in (("0", "الحد الأدنى 1"), ("366", "الحد الأقصى 365"), ("2.5", "أدخل عددًا بدون كسور"),
                           ("abc", "أدخل رقمًا صحيحًا")):
        _, errors = validate("new_sale", new_sale(installation_days=typed), FILES)
        assert errors["installation_days"] == message, typed
