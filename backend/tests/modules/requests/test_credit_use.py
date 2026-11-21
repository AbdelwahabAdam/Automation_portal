"""Paying part of an order out of what the client already holds in Daftra (رصيد العميل, الدائن).

The form shows it as «رصيد سابق» beside what is paid now, and takes off المبلغ المتبقي what the
cash leaves of the total, up to what is held («المخصوم من رصيد العميل»). Submitting puts Daftra's
figure in place of the browser's; approving checks it again before the invoice is made, then pays
that part of the invoice out of the balance. Tried on the live account's test client, 2026-11-21:
a payment of the invoice whose method is client_credit, sent with four fields, saved by Daftra into
its own treasury with no notes and the API as its maker, the client's balance payments untouched.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.core.text import UAE
from app.integrations import daftra
from app.modules.form_engine import sanitize_draft, validate_submission
from app.modules.invoicing import Receipt, payment_of
from app.modules.invoicing.invoice import credit_use_of
from app.modules.models import Request

from ... import seed
from ...conftest import auth
from ...seed import LISTS, PACKAGE_PRICES, PRODUCTS, TODAY, create, payment_wait_is_over, upload

# seed.new_sale comes to 6,000: two packages at 2,800, their inscriptions at 300 each, 200 off
TOTAL = 6000
PAYMENTS = "/api2/invoice_payments.json"
CREDITS = "/api2/client_payments.json"
FILES = {"payment_proof": 1, "design_image": 1}


def validate(data):
    return validate_submission("new_sale", data, FILES, "Sales One", PRODUCTS, PACKAGE_PRICES, LISTS)


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def holding(db, fake_daftra, amount) -> None:
    """Client 4053, in our list and in Daftra, holding this much on no invoice."""
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", name="عميل قديم", category_id=5)
    if amount:
        hold(fake_daftra, amount)


def hold(fake_daftra, amount, client_id=4053):
    payment_id = fake_daftra._new_id()
    fake_daftra.client_payments[payment_id] = {
        "id": payment_id, "code": f"R{payment_id}", "client_id": client_id, "invoice_id": None, "amount": amount,
        "status": "1", "currency_code": "AED", "payment_method": "cash", "transaction_id": "", "staff_id": 15,
        "created": "2026-01-31 15:02:00", "notes": None}


def known_sale(**overrides) -> dict:
    """A sale to client 4053, the balance the form showed for them in previous_credit."""
    return seed.sale_data(phone="0509999999", client_code="4089", customer_name="عميل قديم",
                          create_work_order="لا", installation_days="", **overrides)


def submit(client, user, data, form_type="new_sale"):
    """The request made, its files added, then sent; returns (id, the answer to sending it)."""
    request_id = create(client, user, data, form_type=form_type).json()["id"]
    if form_type == "new_sale":
        assert upload(client, user, request_id, "payment_proof").status_code == 201
        assert upload(client, user, request_id, "design_image").status_code == 201
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(user))
    return request_id, sent


def submitted(client, user, data, form_type="new_sale") -> int:
    request_id, sent = submit(client, user, data, form_type)
    assert sent.status_code == 200, sent.json()
    return request_id


def refreshed(db, request_id) -> Request:
    request = db.get(Request, request_id)
    db.refresh(request)
    return request


def credit_payments(fake_daftra) -> list[dict]:
    return [body["InvoicePayment"] for body in fake_daftra.posted(PAYMENTS)
            if body["InvoicePayment"]["payment_method"] == "client_credit"]


def cash_payments(fake_daftra) -> list[dict]:
    return [body["InvoicePayment"] for body in fake_daftra.posted(PAYMENTS)
            if body["InvoicePayment"]["payment_method"] != "client_credit"]


def balance(client, user, daftra_id=4053):
    response = client.get(f"/api/daftra/clients/{daftra_id}", headers=auth(user))
    assert response.status_code == 200, response.json()
    return response.json()["balance"]["credit"]


def refuse_balance_reads(fake_daftra, monkeypatch):
    """Daftra will not say what the client holds: their payments on no invoice cannot be read."""
    real = type(fake_daftra).__call__

    def refuse(self, method, called, params=None, body=None):
        if method == "GET" and called == CREDITS:
            raise daftra.DaftraError("HTTP 429: ")
        return real(self, method, called, params, body)

    monkeypatch.setattr(type(fake_daftra), "__call__", refuse)


# ---------- the amounts, as the form works them out ----------

def test_the_balance_pays_what_the_cash_leaves_and_no_more_than_is_held():
    clean, errors = validate(seed.new_sale(previous_credit="500", paid_amount="1000"))
    assert errors == {}
    assert (clean["previous_credit"], clean["credit_applied"], clean["remaining_amount"]) == (500, 500, 4500)
    assert "overpaid_amount" not in clean


def test_only_what_is_needed_is_taken_from_the_balance():
    clean, errors = validate(seed.new_sale(previous_credit="500", paid_amount="5800"))
    assert errors == {}
    assert (clean["credit_applied"], clean["remaining_amount"]) == (200, 0)


def test_an_order_the_cash_covers_takes_nothing_from_the_balance():
    clean, errors = validate(seed.new_sale(previous_credit="500", paid_amount=str(TOTAL)))
    assert errors == {}
    assert "credit_applied" not in clean and clean["remaining_amount"] == 0

    # Paid beyond the total: the rest goes to the balance, and nothing is taken from it
    clean, errors = validate(seed.new_sale(previous_credit="500", paid_amount=str(TOTAL + 300)))
    assert errors == {}
    assert "credit_applied" not in clean
    assert (clean["remaining_amount"], clean["overpaid_amount"]) == (0, 300)


def test_with_no_balance_the_amounts_are_as_they_were():
    clean, errors = validate(seed.new_sale())
    assert errors == {}
    assert "previous_credit" not in clean and "credit_applied" not in clean
    assert clean["remaining_amount"] == TOTAL - 1000
    # A balance of 0 takes nothing either
    clean, _ = validate(seed.new_sale(previous_credit="0"))
    assert "credit_applied" not in clean and clean["remaining_amount"] == TOTAL - 1000


def test_what_is_taken_from_the_balance_cannot_be_typed():
    clean, _ = validate(seed.new_sale(previous_credit="500", credit_applied="3000", paid_amount="1000"))
    assert clean["credit_applied"] == 500


def test_a_draft_keeps_the_balance_as_it_was_shown():
    """Not checked until it is sent: submitting puts Daftra's figure in its place."""
    draft = sanitize_draft("new_sale", seed.new_sale(previous_credit="500", credit_applied="500"))
    assert draft["previous_credit"] == "500" and "credit_applied" not in draft


# ---------- submitting: Daftra's figure, never the browser's ----------

def test_the_balance_daftra_holds_is_what_the_request_keeps(client, db, fake_daftra, sales):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    data = db.get(Request, request_id).data
    assert (data["previous_credit"], data["credit_applied"], data["remaining_amount"]) == (500, 500, 4500)


def test_a_balance_the_browser_had_wrong_is_refused(client, db, fake_daftra, sales):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id, sent = submit(client, sales, known_sale(previous_credit="800"))
    assert sent.status_code == 422
    assert sent.json()["detail"]["errors"]["previous_credit"] == (
        "رصيد العميل في دفترة الآن 500 درهم وليس 800. ابحث عن العميل مرة أخرى لتحديث الرصيد ثم راجع المبالغ.")
    assert db.get(Request, request_id).status == "draft"

    # Shown no balance at all, for a client who has one: the amounts were worked out without it
    _, sent = submit(client, sales, known_sale())
    assert sent.json()["detail"]["errors"]["previous_credit"].startswith("رصيد العميل في دفترة الآن 500 درهم وليس 0.")


def test_a_balance_spent_since_it_was_shown_is_refused(client, db, fake_daftra, sales):
    seed.catalog(db)
    holding(db, fake_daftra, 0)
    _, sent = submit(client, sales, known_sale(previous_credit="1,250.5"))
    assert sent.json()["detail"]["errors"]["previous_credit"].startswith(
        "رصيد العميل في دفترة الآن 0 درهم وليس 1,250.50.")


def test_a_balance_daftra_will_not_confirm_is_refused(client, db, fake_daftra, sales, monkeypatch):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    refuse_balance_reads(fake_daftra, monkeypatch)
    _, sent = submit(client, sales, known_sale(previous_credit="500"))
    assert sent.status_code == 422
    assert sent.json()["detail"]["errors"]["previous_credit"] == (
        "تعذر التحقق من رصيد العميل في دفترة الآن. حاول مرة أخرى بعد قليل.")

    # Shown none, the request takes none, and goes
    request_id = submitted(client, sales, known_sale())
    data = db.get(Request, request_id).data
    assert "previous_credit" not in data and "credit_applied" not in data
    assert data["remaining_amount"] == TOTAL - 1000


def test_a_new_client_holds_nothing(client, db, fake_daftra, sales):
    seed.catalog(db)
    _, sent = submit(client, sales, seed.sale_data(previous_credit="500"))
    assert sent.json()["detail"]["errors"]["previous_credit"].startswith("رصيد العميل في دفترة الآن 0 درهم وليس 500.")

    request_id = submitted(client, sales, seed.sale_data())
    assert "previous_credit" not in db.get(Request, request_id).data
    # Daftra is not asked what a client it does not have holds
    assert not [call for call in fake_daftra.calls if call[1] == CREDITS]


# ---------- approving ----------

def test_the_balance_pays_its_part_of_the_invoice_and_the_cash_the_rest(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    assert balance(client, sales) == 500

    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()
    request = refreshed(db, request_id)
    # Exactly what was tried on the live account: no treasury, no notes, no staff member
    assert credit_payments(fake_daftra) == [{"invoice_id": request.daftra_invoice_id, "amount": 500.0,
                                             "payment_method": "client_credit", "date": TODAY}]
    [cash] = cash_payments(fake_daftra)
    assert cash["amount"] == 1000 and cash["payment_method"] == "bank"
    # Made before the cash, as Daftra keeps it
    first, second = fake_daftra.invoices[request.daftra_invoice_id]["payments"]
    assert first["payment_method"] == "client_credit" and second["payment_method"] == "bank"
    assert (first["treasury_id"], first["transaction_id"], first["staff_id"]) == ("2", None, -3)

    # The request keeps its number, apart from the cash receipt's, and the API answers it
    assert (request.daftra_credit_use_id, request.daftra_credit_use_no) == (int(first["id"]), f"R{first['id']}")
    assert request.daftra_receipt_no == f"R{second['id']}"
    assert response.json()["daftra_credit_use_no"] == f"R{first['id']}"
    shown = client.get(f"/api/requests/{request_id}", headers=auth(sales)).json()
    assert shown["daftra_credit_use_no"] == f"R{first['id']}"

    # What is left on the invoice is what the form says is left, and the balance is spent
    invoice = fake_daftra.get_invoice(request.daftra_invoice_id, {}, None)["data"]["Invoice"]
    assert float(invoice["summary_unpaid"]) == 4500
    assert balance(client, sales) == 0
    # Nothing was added to the client's balance payments: spending it is a payment of the invoice
    assert fake_daftra.posted(CREDITS) == []


def test_an_order_the_balance_pays_with_nothing_in_cash(client, db, fake_daftra, sales, manager):
    """اعمال اضافية may be sent with nothing paid now; the balance pays all of it, and there is no
    cash payment and no receipt."""
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    data = tech_works_data(previous_credit="500")
    request_id = submitted(client, sales, data, form_type="tech_extra_works")
    saved = db.get(Request, request_id).data
    assert (saved["total_amount"], saved["credit_applied"], saved["remaining_amount"]) == (412, 412, 0)

    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()
    request = refreshed(db, request_id)
    assert credit_payments(fake_daftra) == [{"invoice_id": request.daftra_invoice_id, "amount": 412.0,
                                             "payment_method": "client_credit", "date": TODAY}]
    assert cash_payments(fake_daftra) == []
    assert request.daftra_credit_use_no and request.daftra_receipt_no is None
    invoice = fake_daftra.get_invoice(request.daftra_invoice_id, {}, None)["data"]["Invoice"]
    assert float(invoice["summary_unpaid"]) == 0
    assert balance(client, sales) == 88


NO_CASH = dict(paid_amount="0", payment_method="", treasury="", payment_date="", payment_reference="")


def submit_without_proof(client, user, data):
    """A sale sent with its design and no proof of payment: there was no payment to prove."""
    request_id = create(client, user, data).json()["id"]
    assert upload(client, user, request_id, "design_image").status_code == 201
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(user))
    return request_id, sent


def test_a_sale_the_balance_pays_part_of_needs_no_cash_no_payment_details_and_no_proof(client, db, fake_daftra,
                                                                                         sales, manager):
    """طلب بيع insists on something paid now. What the client's balance pays is something paid now."""
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id, sent = submit_without_proof(client, sales, known_sale(previous_credit="500", **NO_CASH))
    assert sent.status_code == 200, sent.json()
    saved = db.get(Request, request_id).data
    assert (saved["paid_amount"], saved["credit_applied"], saved["remaining_amount"]) == (0, 500, TOTAL - 500)

    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()
    request = refreshed(db, request_id)
    assert [payment["amount"] for payment in credit_payments(fake_daftra)] == [500.0]
    assert cash_payments(fake_daftra) == []
    assert request.daftra_credit_use_no and request.daftra_receipt_no is None
    assert balance(client, sales) == 0


def test_a_sale_with_no_cash_and_no_balance_is_still_refused(client, db, fake_daftra, sales):
    seed.catalog(db)
    holding(db, fake_daftra, 0)
    request_id, sent = submit_without_proof(client, sales, known_sale(**NO_CASH))
    assert sent.status_code == 422
    assert sent.json()["detail"]["errors"]["paid_amount"] == "يجب أن يكون أكبر من صفر"
    assert db.get(Request, request_id).status == "draft"


def test_cash_paid_on_a_sale_still_needs_its_details_and_its_proof(client, db, fake_daftra, sales):
    """Whatever the balance pays beside it."""
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    data = known_sale(previous_credit="500", **{**NO_CASH, "paid_amount": "1000"})
    _, sent = submit_without_proof(client, sales, data)
    assert sent.status_code == 422
    errors = sent.json()["detail"]["errors"]
    assert {"payment_method", "treasury", "payment_date", "payment_reference", "payment_proof"} <= set(errors)


def test_a_renewal_the_balance_pays_alone(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    holding(db, fake_daftra, 2000)
    data = seed.renewal_data(previous_credit="2000", **NO_CASH)
    request_id = create(client, sales, data, form_type="contract_renewal").json()["id"]
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    saved = db.get(Request, request_id).data
    assert (saved["credit_applied"], saved["remaining_amount"]) == (1680, 0)
    assert approve(client, manager, request_id).status_code == 200
    assert [payment["amount"] for payment in credit_payments(fake_daftra)] == [1680.0]
    assert cash_payments(fake_daftra) == [] and balance(client, sales) == 320


def test_a_balance_gone_since_the_request_was_sent_stops_it_before_the_invoice(client, db, fake_daftra, sales,
                                                                               manager):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    # Spent on something else in the meantime: 200 of it is left
    other = fake_daftra.add_invoice(4053, 300)
    fake_daftra.invoices[other]["payments"].append(
        {"id": fake_daftra._new_id(), "invoice_id": other, "amount": 300, "payment_method": "client_credit",
         "status": "1", "staff_id": 0, "created": "2026-02-04 12:23:51"})

    refused = approve(client, manager, request_id)
    # 409, not 502: the request is wrong, not Daftra
    assert refused.status_code == 409
    assert refused.json()["detail"] == ("رصيد العميل في دفترة الآن 200 درهم، أقل من المخصوم في الطلب (500). "
                                        "أعد الطلب للموظف ليصحح المبالغ.")
    assert fake_daftra.posted("/api2/invoices.json") == [] and fake_daftra.posted(PAYMENTS) == []
    assert refreshed(db, request_id).status == "submitted"


def test_a_balance_daftra_will_not_say_stops_the_approval_before_the_invoice(client, db, fake_daftra, sales,
                                                                             manager, monkeypatch):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    refuse_balance_reads(fake_daftra, monkeypatch)
    refused = approve(client, manager, request_id)
    assert refused.status_code == 502
    assert "تعذر التحقق من رصيد العميل" in refused.json()["detail"]
    assert fake_daftra.posted("/api2/invoices.json") == []


def test_a_balance_payment_whose_answer_was_lost_is_found_again_not_made_twice(client, db, fake_daftra, sales,
                                                                               manager, monkeypatch):
    """It has spent the balance already, so finding it again is what lets the approval go on: the
    check before the invoice would otherwise see too little held."""
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    lose_answer_once(fake_daftra, monkeypatch, lambda fields: fields["payment_method"] == "client_credit")
    failed = approve(client, manager, request_id)
    assert failed.status_code == 502
    request = refreshed(db, request_id)
    assert request.daftra_invoice_id is not None and request.daftra_credit_use_id is None
    assert "رصيد العميل" in request.daftra_error and "انتظر دقيقتين" in request.daftra_error
    assert request.payment_unanswered_at is not None
    [made] = fake_daftra.payments
    assert balance(client, sales) == 0

    assert approve(client, manager, request_id).status_code == 200
    assert len(credit_payments(fake_daftra)) == 1 and len(cash_payments(fake_daftra)) == 1
    request = refreshed(db, request_id)
    assert (request.daftra_credit_use_id, request.daftra_credit_use_no) == (made, f"R{made}")
    assert request.status == "approved" and request.payment_unanswered_at is None


def test_a_balance_payment_daftra_never_recorded_waits_and_is_then_sent_once(client, db, fake_daftra, sales,
                                                                             manager):
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    fake_daftra.fail_once = PAYMENTS                # the first payment sent is the balance's: nothing recorded
    assert approve(client, manager, request_id).status_code == 502
    refused = approve(client, manager, request_id)
    assert refused.status_code == 409
    assert "لن يُخصم من الرصيد مرتين" in refreshed(db, request_id).daftra_error
    assert fake_daftra.posted(PAYMENTS) == []

    payment_wait_is_over(db, request_id)
    assert approve(client, manager, request_id).status_code == 200
    assert len(credit_payments(fake_daftra)) == 1 and len(cash_payments(fake_daftra)) == 1
    assert len(fake_daftra.posted("/api2/invoices.json")) == 1


def test_approving_again_after_a_later_step_failed_takes_the_balance_once(client, db, fake_daftra, sales, manager,
                                                                          monkeypatch):
    """The balance is spent by the first try; the second neither checks it again nor spends it again."""
    seed.catalog(db)
    holding(db, fake_daftra, 500)
    request_id = submitted(client, sales, known_sale(previous_credit="500"))
    real = type(fake_daftra).__call__
    state = {"refused": False}

    def refuse_cash_once(self, method, called, params=None, body=None):
        if (method == "POST" and called == PAYMENTS and body["InvoicePayment"]["payment_method"] == "bank"
                and not state["refused"]):
            state["refused"] = True
            raise daftra.DaftraError("HTTP 400: Bad Request")
        return real(self, method, called, params, body)

    monkeypatch.setattr(type(fake_daftra), "__call__", refuse_cash_once)
    assert approve(client, manager, request_id).status_code == 502
    assert refreshed(db, request_id).daftra_credit_use_id is not None

    assert approve(client, manager, request_id).status_code == 200
    assert approve(client, manager, request_id).status_code != 200      # approved already
    assert len(credit_payments(fake_daftra)) == 1 and len(cash_payments(fake_daftra)) == 1
    assert balance(client, sales) == 0


def test_an_order_with_no_balance_makes_no_balance_payment(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    holding(db, fake_daftra, 0)
    request_id = submitted(client, sales, known_sale())
    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()
    assert credit_payments(fake_daftra) == [] and len(cash_payments(fake_daftra)) == 1
    assert response.json()["daftra_credit_use_no"] is None


def test_a_balance_payment_and_a_cash_one_of_the_same_amount_are_not_taken_for_each_other(
        client, db, fake_daftra, sales, manager, monkeypatch):
    """3,000 from the balance and 3,000 in cash on one invoice: the cash payment's answer lost, the
    next try finds the cash one by its method, not the balance's."""
    seed.catalog(db)
    holding(db, fake_daftra, 3000)
    request_id = submitted(client, sales, known_sale(previous_credit="3000", paid_amount="3000"))
    lose_answer_once(fake_daftra, monkeypatch, lambda fields: fields["payment_method"] == "bank")
    assert approve(client, manager, request_id).status_code == 502
    request = refreshed(db, request_id)
    assert request.daftra_credit_use_id is not None and request.daftra_payment_id is None

    assert approve(client, manager, request_id).status_code == 200
    assert len(credit_payments(fake_daftra)) == 1 and len(cash_payments(fake_daftra)) == 1
    request = refreshed(db, request_id)
    by_method = {p["payment_method"]: int(p["id"]) for p in fake_daftra.invoices[request.daftra_invoice_id]["payments"]}
    assert request.daftra_credit_use_id == by_method["client_credit"]
    assert request.daftra_payment_id == by_method["bank"]


def test_each_finder_knows_its_own_payment_by_its_method():
    request = SimpleNamespace(id=7, created_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    receipt = Receipt(amount="2000", method="تحويل بنكي", treasury=13, date=TODAY, received_by=71, reference="")
    made = datetime.now(UAE).strftime("%Y-%m-%d %H:%M:%S")
    from_credit = {"id": "1", "amount": "2000", "payment_method": "client_credit", "transaction_id": None,
                   "staff_id": "-3", "status": "1", "notes": None, "created": made}
    cash = {**from_credit, "id": "2", "payment_method": "bank", "transaction_id": ""}
    assert payment_of(request, {"InvoicePayment": [from_credit]}, receipt) is None
    assert payment_of(request, {"InvoicePayment": [from_credit, cash]}, receipt) == 2
    assert credit_use_of(request, {"InvoicePayment": [cash]}, Decimal("2000.00")) is None
    assert credit_use_of(request, {"InvoicePayment": [cash, from_credit]}, Decimal("2000.00")) == 1
    # Another amount, or made by hand in Daftra, is not the request's
    assert credit_use_of(request, {"InvoicePayment": [from_credit]}, Decimal("1500.00")) is None
    assert credit_use_of(request, {"InvoicePayment": [{**from_credit, "staff_id": "15"}]}, Decimal("2000.00")) is None


# ---------- helpers ----------

def lose_answer_once(fake_daftra, monkeypatch, which):
    """Daftra records the payment `which` picks, and its answer never reaches the portal."""
    real = type(fake_daftra).__call__
    state = {"lost": False}

    def call(self, method, called, params=None, body=None):
        answer = real(self, method, called, params, body)
        if (method == "POST" and called == PAYMENTS and which(body["InvoicePayment"]) and not state["lost"]):
            state["lost"] = True
            raise daftra.DaftraError("timed out")
        return answer

    monkeypatch.setattr(type(fake_daftra), "__call__", call)


def tech_works_data(**overrides):
    """اعمال اضافية for client 4053 with nothing paid now: 412 of works."""
    data = {"request_date": TODAY, "order_source": "16", "phone": "0509999999", "client_code": "4089",
            "customer_name": "عميل قديم", "technician": "40", "paid_amount": "0",
            "order_lines": [
                {"product_id": "4", "name": "Water Connection Service", "quantity": 2, "base_quantity": None,
                 "group_id": None, "group_name": "", "package_id": None, "unit_price": 6, "details": {}},
                {"product_id": "5", "name": "service", "quantity": 1, "base_quantity": None, "group_id": None,
                 "group_name": "", "package_id": None, "unit_price": 300,
                 "details": {"work_description": "نقل خزان علوي", "work_price": "400"}},
            ]}
    data.update(overrides)
    return data
