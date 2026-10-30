"""The registry of forms: which there are, in what order, and which create anything in Daftra.

A form's key is stored on every request made with it, so renaming one would orphan those
requests. This test is what makes that a failing test rather than a silent loss.
"""

from app.modules.form_engine import all_forms, find, get, keys, visible_forms

# Every form, in the order they appear in النماذج. Add a form here when its folder is added;
# never rename one.
FORMS = [
    "new_sale", "contract_renewal", "maintenance", "balance_payment", "quotation", "quote_to_invoice",
    "order_addition", "order_modification", "return_refund", "tech_cash_collection", "reinstallation",
    "data_entry_error", "pre_sale_inspection", "installation_completed", "contract_service_done",
    "open_ticket", "close_ticket", "daily_visits", "tech_extra_works",
]
# The forms a new request can be made from
VISIBLE = ["new_sale", "contract_renewal", "maintenance", "balance_payment", "quotation", "tech_extra_works"]
# The forms approving creates something in Daftra for
INVOICED = ["new_sale", "contract_renewal", "maintenance", "balance_payment", "quotation", "tech_extra_works"]


def test_every_form_is_registered_once_in_order():
    assert keys() == FORMS


def test_the_visible_forms_are_the_ones_a_request_can_be_made_from():
    assert [form.key for form in visible_forms()] == VISIBLE


def test_exactly_the_invoiced_forms_create_something_in_daftra():
    assert [form.key for form in all_forms() if form.on_approve] == INVOICED
    assert [form.key for form in all_forms() if form.invoiced] == INVOICED


def test_every_form_has_a_label_an_icon_and_sections():
    for form in all_forms():
        assert form.label, f"{form.key} has no label"
        assert form.icon, f"{form.key} has no icon"
        assert form.sections, f"{form.key} has no sections"
        assert form.fields(), f"{form.key} has no fields"


def test_every_invoiced_form_says_what_approving_creates():
    """The note the form shows the manager before approving it."""
    for form in all_forms():
        assert bool(form.daftra_note) == form.invoiced, f"{form.key}: note and invoiced disagree"


def test_the_api_shape_is_what_the_screens_read():
    shape = get("new_sale").as_api()
    assert set(shape) == {"key", "label", "icon", "description", "sections", "invoiced", "daftra_note", "hidden"}
    assert shape["invoiced"] is True and shape["hidden"] is False
    # A form nobody may fill yet: hidden, and the screens grey it out rather than offer it
    assert get("quote_to_invoice").as_api()["hidden"] is True


def test_a_form_that_is_not_registered_is_not_invented():
    assert find("no_such_form") is None


def test_only_balance_payment_checks_more_than_its_fields():
    """The one check the field rules cannot express; every other form has none."""
    assert [form.key for form in all_forms() if form.validate] == ["balance_payment"]
