"""The form definitions and their validation (app.forms), without the database."""

from datetime import date, timedelta

from app import forms
from app.forms import FORM_TYPES, form_fields, package_colors, package_quantity, sanitize_draft, validate_submission

PACKAGE = "باقة برادة سقيا الخير - 3 صنابير - أسود"
PRODUCTS = {
    "1": {"id": 1, "name": "WATER COOLER BLACK 3 T", "price": 1000, "maintenance_group": None},
    "2": {"id": 2, "name": "exchange contract", "price": 1200, "maintenance_group": None},
    "3": {"id": 3, "name": "RO .PP 10", "price": 50, "maintenance_group": "الفلاتر"},
}
PACKAGE_PRICES = {("10", "1"): 2000.0, ("10", "2"): 800.0}
LISTS = {"daftra_order_source": {16: "Sales-جديد"}, "daftra_treasury": {13: "ADIB NEW CURRENT", 9: "خزينه المكتب"},
         "daftra_client_category": {5: "العين العامره"}}
TODAY = date.today().isoformat()


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
        "category": "5", "area": "منطقة العين", "emirate": "أبوظبي", "street": "شارع 1", "house": "فيلا 2",
        "location_url": "https://maps.google.com/?q=24.17870,55.60451", "coordinates": "24.1787, 55.6045",
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
        "category": "5", "area": "منطقة العين", "emirate": "أبوظبي", "coordinates": "24.1, 55.6",
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
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
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
            "area": "منطقة العين", "emirate": "أبوظبي", "coordinates": "1.1, 2.2", "cooler_type": "سقيا",
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
