"""The shared sections and their switches (form_engine/switches.py, sections.py): what each value
does, and that a mistake is refused when the form loads.

What each form asks is pinned by its snapshot (tests/forms/test_fields_snapshot.py). While the
forms were being moved onto the switches, a second half of this file proved that every way the old
builders were called gave the very same section through the new ones; it went with them.
"""

import pytest

from app.modules.form_engine import HIDE, NEW_CLIENT, PAID, REQUIRED, REQUIRED_IF, SHOW, f, shared, switched

# ---------- the switches ----------


def test_hide_leaves_the_field_out_and_show_keeps_it_optional():
    built = switched("س", (HIDE, f("a", "A", required=True)), (SHOW, f("b", "B", required=True)))
    assert [field["name"] for field in built["fields"]] == ["b"]
    assert built["fields"][0]["required"] is False


def test_required_and_required_if_replace_whatever_the_field_said():
    built = switched("س", (REQUIRED, f("a", "A", required_if=PAID)), (REQUIRED_IF(PAID), f("b", "B", required=True)))
    first, second = built["fields"]
    assert first["required"] is True and "required_if" not in first
    assert second["required"] is False and second["required_if"] == PAID


def test_new_client_marks_the_field_as_asked_of_a_new_client_only():
    [field] = switched("س", (NEW_CLIENT(SHOW), f("email", "E", "email")))["fields"]
    assert field["new_client"] is True and field["required"] is False


def test_a_switch_that_is_not_one_is_refused():
    with pytest.raises(TypeError, match="HIDE, SHOW, REQUIRED"):
        switched("س", (True, f("a", "A")))
    with pytest.raises(ValueError):
        REQUIRED_IF("paid_amount")
    with pytest.raises(ValueError):
        NEW_CLIENT(HIDE)


def test_a_section_with_a_field_left_unnamed_does_not_load():
    with pytest.raises(TypeError, match="email"):
        shared.client(phone=REQUIRED, phone2=SHOW, client_code=SHOW, customer_name=REQUIRED,
                      customer_type=SHOW, gender=SHOW)


def test_a_misspelt_field_does_not_load():
    with pytest.raises(TypeError, match="phone_2"):
        shared.client(phone=REQUIRED, phone_2=SHOW, client_code=SHOW, customer_name=REQUIRED,
                      customer_type=SHOW, gender=SHOW, email=HIDE)


def test_a_label_for_a_field_the_section_has_not_got_is_refused():
    with pytest.raises(TypeError, match="nickname"):
        shared.notes(notes=SHOW, labels={"nickname": "x"})


def test_amounts_refuses_what_cannot_be_worked_out():
    base = dict(subtotal_amount=SHOW, total_amount=SHOW, discount_label=HIDE, discount_amount=SHOW,
                discount_percent=HIDE, discount_approved_by=SHOW, paid_amount=REQUIRED, remaining_amount=SHOW,
                remaining_due_date=SHOW)
    shared.amounts(**base)
    # نسبة الخصم is a share of the subtotal, beside قيمة الخصم: with either hidden it has nothing to be
    shared.amounts(**{**base, "discount_percent": SHOW})
    with pytest.raises(TypeError, match="discount_percent"):
        shared.amounts(**{**base, "discount_percent": SHOW, "subtotal_amount": HIDE})
    with pytest.raises(TypeError, match="paid_amount"):
        shared.amounts(**{**base, "paid_amount": HIDE})
    with pytest.raises(TypeError, match="total_amount=SHOW"):
        shared.amounts(**{**base, "total_amount": REQUIRED})
    with pytest.raises(TypeError, match="discount_amount is hidden"):
        shared.amounts(**{**base, "discount_amount": HIDE})


def test_amounts_takes_more_than_the_total_only_where_the_form_says_so():
    base = dict(subtotal_amount=SHOW, total_amount=SHOW, discount_label=HIDE, discount_amount=SHOW,
                discount_percent=HIDE, discount_approved_by=SHOW, paid_amount=REQUIRED, remaining_amount=SHOW,
                remaining_due_date=SHOW)
    strict = {field["name"]: field for field in shared.amounts(**base)["fields"]}
    assert "overpaid_amount" not in strict
    assert strict["remaining_amount"]["negative_message"] == "المبلغ المدفوع أكبر من قيمة الطلب"

    names = [field["name"] for field in shared.amounts(**base, may_overpay=True)["fields"]]
    fields = {field["name"]: field for field in shared.amounts(**base, may_overpay=True)["fields"]}
    # Nothing is left of an order paid beyond its total, and the rest is a line of its own right under it
    assert "negative_message" not in fields["remaining_amount"] and fields["remaining_amount"]["floor"] == 0
    assert names[names.index("remaining_amount") + 1] == "overpaid_amount"
    extra = fields["overpaid_amount"]
    assert (extra["computed"], extra["floor"], extra["hide_when_zero"]) == (["paid_amount", "total_amount"], 0, True)
    # It is what was paid beyond the total: with nothing paid on the form there is no such thing
    with pytest.raises(TypeError, match="may_overpay"):
        shared.amounts(**{**base, "paid_amount": HIDE, "remaining_amount": HIDE, "remaining_due_date": HIDE},
                       may_overpay=True)


def test_amounts_takes_the_clients_balance_only_where_the_form_says_so():
    base = dict(subtotal_amount=SHOW, total_amount=SHOW, discount_label=HIDE, discount_amount=SHOW,
                discount_percent=HIDE, discount_approved_by=SHOW, paid_amount=REQUIRED, remaining_amount=SHOW,
                remaining_due_date=SHOW)
    plain = {field["name"]: field for field in shared.amounts(**base)["fields"]}
    assert "previous_credit" not in plain and "credit_applied" not in plain
    assert plain["remaining_amount"]["computed"] == ["total_amount", "paid_amount"]

    section = shared.amounts(**base, may_overpay=True, takes_credit=True)
    names = [field["name"] for field in section["fields"]]
    fields = {field["name"]: field for field in section["fields"]}
    # «رصيد سابق» beside what is paid now; what the order takes of it just before what is left,
    # which is worked out after it (computed fields are worked out in the order they stand)
    assert names[names.index("paid_amount") + 1] == "previous_credit"
    assert names[names.index("remaining_amount") - 1] == "credit_applied"
    assert names[names.index("remaining_amount") + 1] == "overpaid_amount"
    assert fields["previous_credit"] == {"name": "previous_credit", "label": "رصيد سابق", "type": "number",
                                         "required": False, "money": True, "client_credit": True,
                                         "pair_with": "paid_amount"}
    assert fields["credit_applied"] == {"name": "credit_applied", "label": "المخصوم من رصيد العميل",
                                        "type": "number", "required": False, "money": True,
                                        "computed": ["total_amount", "paid_amount"], "floor": 0,
                                        "cap": "previous_credit", "hide_when_zero": True}
    assert fields["remaining_amount"]["computed"] == ["total_amount", "paid_amount", "credit_applied"]
    assert fields["remaining_amount"]["floor"] == 0

    # Without may_overpay what is left still may not go below 0
    strict = {field["name"]: field for field in shared.amounts(**base, takes_credit=True)["fields"]}
    assert strict["remaining_amount"]["negative_message"] == "المبلغ المدفوع أكبر من قيمة الطلب"
    assert "overpaid_amount" not in strict and "credit_applied" in strict
    # It pays what paid_amount leaves: with nothing paid on the form there is no such thing
    with pytest.raises(TypeError, match="takes_credit"):
        shared.amounts(**{**base, "paid_amount": HIDE, "remaining_amount": HIDE, "remaining_due_date": HIDE},
                       takes_credit=True)
    with pytest.raises(TypeError, match="takes_credit"):
        shared.amounts(**{**base, "remaining_amount": HIDE, "remaining_due_date": HIDE}, takes_credit=True)


def test_request_info_asks_one_order_source_at_most():
    with pytest.raises(TypeError, match="not both"):
        shared.request_info(request_date=REQUIRED, employee_name=SHOW, order_source=REQUIRED, source=REQUIRED)
