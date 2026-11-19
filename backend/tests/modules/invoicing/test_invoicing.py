"""What invoicing holds that is ours rather than Daftra's."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.text import UAE
from app.modules.form_engine import PAYMENT_METHODS
from app.modules.invoicing import PAYMENT_METHOD_KEYS, Receipt, marker, payment_of


def test_payment_methods_cover_every_choice():
    """Every payment method a form offers has a Daftra key, and no key is left over.

    The mapping used to be zipped against PAYMENT_METHODS by position, so reordering the
    choices would have sent payments to the wrong Daftra key without a word. It is written
    out in full now, and this is what keeps the two in step.
    """
    assert sorted(PAYMENT_METHOD_KEYS) == sorted(PAYMENT_METHODS)


def test_the_daftra_keys_are_the_ones_the_account_records():
    """The keys as found on the account's existing payments (Tabby is recorded as "visa")."""
    assert [PAYMENT_METHOD_KEYS[method] for method in PAYMENT_METHODS] == [
        "bank", "cash", "GEIDEA", "visa", "_tamara", "Apple_pay",
    ]


# ---------- a payment the request already made, found again without its marker ----------
# Request 204, invoice 06651: the second try of the approval sent the payment and gave up waiting;
# Daftra recorded it a minute later, with no notes (it keeps none), and the third try paid again.

REQUEST = SimpleNamespace(id=204, created_at=datetime.now(timezone.utc) - timedelta(minutes=40))
RECEIPT = Receipt(amount="2000", method="تحويل بنكي", treasury=2, date="2026-11-18", received_by=71,
                  reference="530P1F40A4248E6F")


def recorded(**changes) -> dict:
    """The payment as the invoice carries it in Daftra: made by the API, its notes empty."""
    return {"id": "30232", "code": "030226", "amount": "2000", "payment_method": "bank",
            "transaction_id": "530P1F40A4248E6F", "staff_id": "-3", "status": "1", "notes": None,
            "created": datetime.now(UAE).strftime("%Y-%m-%d %H:%M:%S"), **changes}


def test_the_payment_is_known_by_its_amount_method_and_transfer_number():
    assert payment_of(REQUEST, {"InvoicePayment": [recorded()]}, RECEIPT) == 30232
    # Daftra writes the amount as it likes; it is the same money
    assert payment_of(REQUEST, {"InvoicePayment": [recorded(amount="2000.00")]}, RECEIPT) == 30232
    # Made by the receipt's own staff member, should Daftra ever keep the one it is sent
    assert payment_of(REQUEST, {"InvoicePayment": [recorded(staff_id="71")]}, RECEIPT) == 30232


@pytest.mark.parametrize("changes", [
    {"amount": "2500"},                        # another amount
    {"payment_method": "cash"},                # another way of paying
    {"transaction_id": "530PEC123532A266"},    # another transfer
    {"transaction_id": None},
    {"staff_id": "38"},                        # made by hand in Daftra, by someone else
    {"status": "0"},                           # not a payment that went through
    {"created": "2026-01-05 10:00:00"},        # older than the request: not its own
])
def test_a_payment_that_differs_in_any_of_them_is_not_the_requests(changes):
    assert payment_of(REQUEST, {"InvoicePayment": [recorded(**changes)]}, RECEIPT) is None


def test_a_cash_payment_with_no_number_is_matched_on_having_none():
    cash = Receipt(amount="500", method="نقدًا", treasury=9, date="2026-11-18", received_by=71)
    plain = recorded(amount="500", payment_method="cash", transaction_id="")
    assert payment_of(REQUEST, {"InvoicePayment": [plain]}, cash) == 30232
    assert payment_of(REQUEST, {"InvoicePayment": [{**plain, "transaction_id": "X-1"}]}, cash) is None


def test_the_marker_still_finds_it_where_daftra_keeps_notes_and_alone_needs_no_receipt():
    marked = recorded(amount="1", notes=f"{marker(REQUEST)}\nملاحظات الموظف")
    assert payment_of(REQUEST, {"InvoicePayment": [marked]}, RECEIPT) == 30232
    assert payment_of(REQUEST, {"InvoicePayment": [marked]}) == 30232
    # Without the receipt there is nothing to match an unmarked one on
    assert payment_of(REQUEST, {"InvoicePayment": [recorded()]}) is None
    assert payment_of(REQUEST, {}, RECEIPT) is None
