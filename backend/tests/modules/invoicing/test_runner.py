"""The runner that makes a form's documents (modules/invoicing/runner.py): its own rules.

What each document sends is pinned by the payload tests of the forms that make it; these are the
rules about the list: everything is built before anything is sent, a form may leave a document
out for one request, and the documents that depend on an invoice need one before them.
"""

from types import SimpleNamespace

import pytest

from app.core.errors import SyncError
from app.modules.invoicing import ClientRecord, Receipt, WorkOrder, run


def ctx():
    # Building touches nothing of the request, so none is needed to show that nothing was sent
    return SimpleNamespace(request=None, db=None, reviewer=None, data={})


def a_client(_):
    return ClientRecord(phone="0501234567", name="عميل")


def test_a_failing_check_stops_the_approval_before_anything_is_sent(fake_daftra):
    def refused(_):
        raise SyncError("هذه المنتجات غير مربوطة بمنتج في دفترة")

    with pytest.raises(SyncError, match="غير مربوطة"):
        run(ctx(), [a_client, refused])
    assert fake_daftra.calls == []


def test_an_unknown_payment_method_is_refused_while_building():
    with pytest.raises(SyncError, match="غير معروفة لدفترة"):
        Receipt(amount=100, method="بالشيك", treasury=1, date="2026-11-13", received_by=71)
    # Nothing paid: no method needed
    Receipt(amount=0, method="", treasury=None, date="", received_by=71)


def test_a_document_left_out_for_this_request_is_skipped(fake_daftra):
    assert run(ctx(), [lambda _: None, lambda _: None]) == {}
    assert fake_daftra.calls == []


def test_a_receipt_needs_the_invoice_it_pays_before_it(fake_daftra):
    receipt = Receipt(amount=100, method="تحويل بنكي", treasury=13, date="2026-11-13", received_by=71)
    with pytest.raises(TypeError, match="pays the Invoice"):
        run(ctx(), [lambda _: receipt])
    assert fake_daftra.calls == []


def test_a_work_order_needs_an_invoice_before_it(fake_daftra):
    order = WorkOrder(title="باقة", days=20, description="", fields={}, printed={})
    with pytest.raises(TypeError, match="linked to an Invoice"):
        run(ctx(), [lambda _: order])
    assert fake_daftra.calls == []


def test_something_that_is_not_a_document_is_refused(fake_daftra):
    with pytest.raises(TypeError, match="not a document"):
        run(ctx(), [lambda _: {"Invoice": {}}])
