"""نسبة الخصم beside قيمة الخصم: either is typed, the other follows (validation.discount_from_percent)."""

from app.modules.form_engine import form_fields, sanitize_draft, validate_submission
from app.modules.form_engine.validation import whole_dirhams

from ...seed import LISTS, PACKAGE_PRICES, PRODUCTS, new_sale

FILES = {"payment_proof": 1, "design_image": 1}
# The seed's order: two packages of (2000 + 800), and their inscription of 300 once each
SUBTOTAL = 6200.0


def validate(**overrides):
    return validate_submission("new_sale", new_sale(**overrides), FILES, "Sales One",
                               PRODUCTS, PACKAGE_PRICES, LISTS)


def by_percent(percent, **more):
    return validate(**{"discount_amount": "", "discount_percent": percent, "discount_percent_basis": "percent", **more})


def test_the_seed_order_is_the_subtotal_these_tests_assume():
    clean, errors = validate()
    assert errors == {} and clean["subtotal_amount"] == SUBTOTAL


# ---------- a percentage typed ----------

def test_a_percentage_gives_the_amount_and_the_total():
    clean, errors = by_percent("10")
    assert errors == {}
    assert clean["discount_amount"] == 620.0 and clean["discount_percent"] == 10.0
    assert clean["total_amount"] == SUBTOTAL - 620
    # Which one was typed is kept with the request, so a return for changes follows the same one
    assert clean["discount_percent_basis"] == "percent"


def test_a_percentage_gives_whole_dirhams():
    clean, _ = by_percent("12.345")
    # The percentage to two places (12.35), and 12.35% of 6200 is 765.70: the dirham, 766
    assert clean["discount_percent"] == 12.35 and clean["discount_amount"] == 766.0


def test_a_half_dirham_goes_up():
    assert [whole_dirhams(v) for v in (0.5, 2.5, 754.4, 754.5, 754.6)] == [1.0, 3.0, 754.0, 755.0, 755.0]


def test_the_percentage_typed_stays_whatever_amount_the_browser_sent():
    """The browser works the amount out too; the server works it out again from its own subtotal."""
    clean, _ = by_percent("10", discount_amount="999")
    assert clean["discount_amount"] == 620.0


def test_emptying_the_percentage_takes_its_amount_away():
    clean, errors = by_percent("", discount_amount="620", discount_label="", discount_approved_by="")
    assert "discount_amount" not in clean and "discount_percent" not in clean
    assert clean["total_amount"] == SUBTOTAL


def test_no_more_than_the_whole_order():
    _, errors = by_percent("101")
    assert errors["discount_percent"] == "الحد الأقصى 100"
    # 100% is a percentage the field takes. (طلب بيع itself still wants something paid now, so the
    # request as a whole is refused — that is the form's rule, not this field's.)
    clean, errors = by_percent("100", paid_amount="0")
    assert "discount_percent" not in errors and "discount_amount" not in errors
    assert clean["discount_amount"] == SUBTOTAL and clean["total_amount"] == 0


# ---------- an amount typed ----------

def test_an_amount_gives_its_percentage_to_two_places():
    clean, errors = validate(discount_amount="200")
    assert errors == {}
    # 200 of 6200 is 3.2258…%
    assert clean["discount_amount"] == 200.0 and clean["discount_percent"] == 3.23
    assert clean["discount_percent_basis"] == "amount"
    assert clean["total_amount"] == SUBTOTAL - 200


def test_the_amount_typed_stays_whatever_percentage_the_browser_sent():
    clean, _ = validate(discount_amount="620", discount_percent="50", discount_percent_basis="amount")
    assert clean["discount_amount"] == 620.0 and clean["discount_percent"] == 10.0


def test_an_unknown_basis_counts_as_the_amount():
    clean, _ = validate(discount_amount="620", discount_percent="50", discount_percent_basis="anything")
    assert clean["discount_amount"] == 620.0 and clean["discount_percent_basis"] == "amount"


def test_no_discount_means_no_percentage_and_nothing_remembered():
    clean, errors = validate(discount_amount="", discount_label="", discount_approved_by="", discount_percent="")
    assert errors == {}
    assert "discount_percent" not in clean and "discount_percent_basis" not in clean


# ---------- drafts and forms ----------

def test_a_draft_remembers_which_one_was_typed():
    draft = sanitize_draft("new_sale", {**new_sale(), "discount_percent": "10", "discount_percent_basis": "percent"})
    assert draft["discount_percent"] == "10" and draft["discount_percent_basis"] == "percent"
    # A basis that is neither of the two is not kept
    assert "discount_percent_basis" not in sanitize_draft("new_sale", {**new_sale(), "discount_percent_basis": "x"})


def test_the_forms_with_a_subtotal_have_it_and_the_others_do_not():
    def has(form):
        return any(spec["name"] == "discount_percent" for spec in form_fields(form))

    for form in ("new_sale", "online_sale", "quotation", "contract_renewal", "maintenance"):
        assert has(form), form
    # A discount on an addition or a change, with no order total to be a percentage of
    for form in ("order_addition", "quote_to_invoice", "order_modification"):
        assert not has(form), form


def test_the_percentage_sits_right_after_the_amount_and_says_what_it_is_of():
    names = [spec["name"] for spec in form_fields("new_sale")]
    assert names.index("discount_percent") == names.index("discount_amount") + 1
    spec = next(s for s in form_fields("new_sale") if s["name"] == "discount_percent")
    assert (spec["percent_of"], spec["amount_field"], spec["min"], spec["max"]) == ("subtotal_amount", "discount_amount", 0, 100)


def test_a_discount_given_as_a_percentage_still_needs_its_name_and_who_approved_it():
    """اسم الخصم and the approver are required by «قيمة الخصم > 0», which a percentage now gives."""
    _, errors = by_percent("10", discount_label="", discount_approved_by="")
    assert errors.get("discount_label") == "مطلوب" and errors.get("discount_approved_by") == "مطلوب"
