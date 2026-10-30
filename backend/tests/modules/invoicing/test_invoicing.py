"""What invoicing holds that is ours rather than Daftra's."""

from app.forms import PAYMENT_METHODS
from app.modules.invoicing import PAYMENT_METHOD_KEYS


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
