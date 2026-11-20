"""Paying beyond the total, and the client's balance in Daftra (رصيد العميل, الدائن on their page).

What goes beyond an order's total is not put on its invoice, where it would stand as a negative
remainder until someone settled it by hand: it is recorded as the client's own balance, a payment
of theirs on no invoice. Tried on the live account's test client, 2026-11-20: Daftra keeps such a
payment's status and currency only when they are sent, lists it only with a status, and counts it
in الدائن only with a currency.
"""

from app.integrations import daftra
from app.modules.models import Request

from ... import seed
from ...conftest import auth
from ...seed import create, payment_wait_is_over, sale_data, submitted_sale, upload

# seed.new_sale comes to 6,000: two packages at 2,800, their inscriptions at 300 each, 200 off
TOTAL = 6000
CREDITS = "/api2/client_payments.json"


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def overpaid_sale(client, db, sales, extra=300, **overrides) -> int:
    return submitted_sale(client, db, sales, paid_amount=str(TOTAL + extra), create_work_order="لا",
                          installation_days="", **overrides)


def answer_lost_once(fake_daftra, monkeypatch, path):
    """Daftra makes the record, and its answer never reaches the portal."""
    real = type(fake_daftra).__call__
    state = {"lost": False}

    def call(self, method, called, params=None, body=None):
        answer = real(self, method, called, params, body)
        if method == "POST" and called == path and not state["lost"]:
            state["lost"] = True
            raise daftra.DaftraError("timed out")
        return answer

    monkeypatch.setattr(type(fake_daftra), "__call__", call)


# ---------- the form ----------

def test_what_is_paid_beyond_the_total_is_worked_out_and_nothing_is_left(client, db, sales):
    seed.catalog(db)
    request_id = overpaid_sale(client, db, sales)
    data = db.get(Request, request_id).data
    assert (data["total_amount"], data["paid_amount"]) == (TOTAL, TOTAL + 300)
    assert (data["remaining_amount"], data["overpaid_amount"]) == (0, 300)


def test_an_order_paid_no_more_than_its_total_holds_no_extra(client, db, sales):
    seed.catalog(db)
    exact = submitted_sale(client, db, sales, paid_amount=str(TOTAL))
    part = submitted_sale(client, db, sales, phone="0501112223")
    assert "overpaid_amount" not in db.get(Request, exact).data
    assert db.get(Request, exact).data["remaining_amount"] == 0
    assert "overpaid_amount" not in db.get(Request, part).data
    assert db.get(Request, part).data["remaining_amount"] == TOTAL - 1000


def test_the_extra_cannot_be_typed(client, db, sales):
    """It is worked out on the server whatever the browser sends."""
    seed.catalog(db)
    request_id = create(client, sales, sale_data(overpaid_amount="5000")).json()["id"]
    upload(client, sales, request_id, "payment_proof")
    upload(client, sales, request_id, "design_image")
    sent = client.put(f"/api/requests/{request_id}", json={"data": sale_data(overpaid_amount="5000"), "action": "submit"},
                      headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    assert "overpaid_amount" not in db.get(Request, request_id).data


# ---------- approving ----------

def test_the_invoice_is_paid_its_total_and_the_rest_goes_to_the_clients_balance(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = overpaid_sale(client, db, sales)
    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()

    [payment] = fake_daftra.posted("/api2/invoice_payments.json")
    assert payment["InvoicePayment"]["amount"] == TOTAL
    [credit] = fake_daftra.posted(CREDITS)
    request = db.get(Request, request_id)
    db.refresh(request)
    sent = credit["ClientPayment"]
    assert sent == {
        "client_id": request.daftra_client_id, "amount": 300.0, "payment_method": "bank", "treasury_id": 13,
        "date": seed.TODAY, "transaction_id": "TRX-1",
        # Without these two Daftra saves it and shows it nowhere: not listed, not counted in الدائن
        "status": 1, "currency_code": "AED",
        "notes": f"PORTAL-{request_id}", "staff_id": sent["staff_id"],
    }
    # The invoice is paid in full and owes nothing back
    invoice = fake_daftra.get_invoice(request.daftra_invoice_id, {}, None)["data"]["Invoice"]
    assert float(invoice["summary_unpaid"]) == 0

    # Two receipts in Daftra, and the request keeps both numbers
    [made] = fake_daftra.client_payments
    assert (request.daftra_credit_id, request.daftra_credit_no) == (made, f"R{made}")
    assert request.daftra_receipt_no and request.daftra_receipt_no != request.daftra_credit_no
    assert response.json()["daftra_credit_no"] == f"R{made}"


def test_an_order_paid_no_more_than_its_total_makes_no_balance_payment(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()
    assert fake_daftra.posted(CREDITS) == [] and response.json()["daftra_credit_no"] is None
    [payment] = fake_daftra.posted("/api2/invoice_payments.json")
    assert payment["InvoicePayment"]["amount"] == 1000


def test_a_balance_payment_whose_answer_was_lost_is_found_again_not_made_twice(client, db, fake_daftra, sales,
                                                                               manager, monkeypatch):
    """As an invoice's payment is (request 204): Daftra keeps no notes on it, so it is known by its
    amount, method and transfer number among the client's payments on no invoice."""
    seed.catalog(db)
    request_id = overpaid_sale(client, db, sales)
    answer_lost_once(fake_daftra, monkeypatch, CREDITS)
    assert approve(client, manager, request_id).status_code == 502
    request = db.get(Request, request_id)
    db.refresh(request)
    assert request.daftra_payment_id is not None and request.daftra_credit_id is None
    assert "رصيد العميل" in request.daftra_error and "انتظر دقيقتين" in request.daftra_error
    [made] = fake_daftra.client_payments

    assert approve(client, manager, request_id).status_code == 200
    assert len(fake_daftra.posted(CREDITS)) == 1 and len(fake_daftra.posted("/api2/invoice_payments.json")) == 1
    db.refresh(request)
    assert (request.daftra_credit_id, request.daftra_credit_no) == (made, f"R{made}")
    assert request.status == "approved" and request.payment_unanswered_at is None


def test_a_balance_payment_daftra_never_recorded_waits_and_is_then_sent_once(client, db, fake_daftra, sales, manager,
                                                                             monkeypatch):
    seed.catalog(db)
    request_id = overpaid_sale(client, db, sales)
    real = type(fake_daftra).__call__
    state = {"failed": False}

    def call(self, method, called, params=None, body=None):
        # The sending alone fails, and records nothing: the list is read before it (credit_of)
        if method == "POST" and called == CREDITS and not state["failed"]:
            state["failed"] = True
            raise daftra.DaftraError("timed out")
        return real(self, method, called, params, body)

    monkeypatch.setattr(type(fake_daftra), "__call__", call)
    assert approve(client, manager, request_id).status_code == 502
    refused = approve(client, manager, request_id)
    assert refused.status_code == 409
    request = db.get(Request, request_id)
    db.refresh(request)
    assert "لن تُسجَّل مرتين" in request.daftra_error
    assert fake_daftra.posted(CREDITS) == []

    payment_wait_is_over(db, request_id)
    assert approve(client, manager, request_id).status_code == 200
    assert len(fake_daftra.posted(CREDITS)) == 1 and len(fake_daftra.posted("/api2/invoice_payments.json")) == 1


def test_a_like_balance_payment_made_by_hand_is_not_taken_for_the_requests(client, db, fake_daftra, sales, manager):
    """Same client, amount, method and transfer number — and made by a person in Daftra, not the API."""
    seed.catalog(db)
    seed.existing_client(db, phone="0501234567")
    fake_daftra.add_client(4053, "0501234567", name="عميل تجريبي", category_id=5)
    fake_daftra.client_payments[900] = {
        "id": 900, "code": "R900", "client_id": 4053, "invoice_id": None, "amount": 300, "status": "1",
        "currency_code": "AED", "payment_method": "bank", "transaction_id": "TRX-1", "staff_id": 15,
        "created": "2030-01-01 10:00:00", "notes": None}
    request_id = overpaid_sale(client, db, sales, client_code="4089")
    assert approve(client, manager, request_id).status_code == 200
    request = db.get(Request, request_id)
    db.refresh(request)
    assert request.daftra_client_id == 4053
    assert len(fake_daftra.posted(CREDITS)) == 1 and request.daftra_credit_id != 900


# ---------- the client's balance, where a client is searched for ----------

def details(client, user, daftra_id=4053):
    response = client.get(f"/api/daftra/clients/{daftra_id}", headers=auth(user))
    assert response.status_code == 200, response.json()
    return response.json()


def held(fake_daftra, amount, client_id=4053, status="1"):
    payment_id = fake_daftra._new_id()
    fake_daftra.client_payments[payment_id] = {
        "id": payment_id, "code": f"R{payment_id}", "client_id": client_id, "invoice_id": None, "amount": amount,
        "status": status, "currency_code": "AED", "payment_method": "cash", "transaction_id": "", "staff_id": 15,
        "created": "2026-01-31 15:02:00", "notes": None}
    return payment_id


def spend(fake_daftra, invoice_id, amount, method="client_credit"):
    fake_daftra.invoices[invoice_id]["payments"].append(
        {"id": fake_daftra._new_id(), "invoice_id": invoice_id, "amount": amount, "payment_method": method,
         "status": "1", "staff_id": 0, "created": "2026-02-04 12:23:51"})


def test_a_client_with_nothing_owed_and_nothing_held_has_neither(client, fake_daftra, sales):
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    assert details(client, sales)["balance"] == {"owed": 0, "credit": 0}


def test_the_balance_is_what_their_invoices_owe_and_what_they_hold(client, fake_daftra, sales):
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    fake_daftra.add_client(77, "0508888888")
    fake_daftra.add_invoice(4053, 3150, paid=1900)
    fake_daftra.add_invoice(4053, 800)
    fake_daftra.add_invoice(4053, 999, draft="1")       # a draft owes nothing
    held(fake_daftra, 300)
    held(fake_daftra, 200)
    held(fake_daftra, 5000, client_id=77)               # another client's
    held(fake_daftra, 700, status=None)                 # saved with no status: Daftra does not list it
    assert details(client, sales)["balance"] == {"owed": 2050, "credit": 500}


def test_what_they_spent_of_their_balance_is_no_longer_held(client, fake_daftra, sales):
    """Live, client 2487: 7,350 paid on account, and their invoice paid out of it four days later.
    Daftra leaves the first payment as it was and adds one of method client_credit to the invoice."""
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    paid_from_it = fake_daftra.add_invoice(4053, 7350)
    spend(fake_daftra, paid_from_it, 7350)
    held(fake_daftra, 7350)
    assert details(client, sales)["balance"] == {"owed": 0, "credit": 0}

    # Part of it spent, and an invoice paid in cash that takes nothing from it
    held(fake_daftra, 1000)
    other = fake_daftra.add_invoice(4053, 600)
    spend(fake_daftra, other, 250)
    spend(fake_daftra, other, 350, method="cash")
    assert details(client, sales)["balance"] == {"owed": 0, "credit": 750}


def test_more_spent_than_the_list_shows_held_is_no_balance_not_a_negative_one(client, fake_daftra, sales):
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    held(fake_daftra, 1500)
    spend(fake_daftra, fake_daftra.add_invoice(4053, 4750), 4750)
    assert details(client, sales)["balance"] == {"owed": 0, "credit": 0}


def test_every_page_of_a_clients_payments_is_counted(client, fake_daftra, sales):
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    for _ in range(117):
        held(fake_daftra, 10)
    assert details(client, sales)["balance"] == {"owed": 0, "credit": 1170}


def test_daftra_not_saying_what_they_hold_still_shows_what_they_owe(client, fake_daftra, sales, monkeypatch):
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    fake_daftra.add_invoice(4053, 800)
    real = type(fake_daftra).__call__

    def refuse(self, method, called, params=None, body=None):
        if called == CREDITS:
            raise daftra.DaftraError("HTTP 429: ")
        return real(self, method, called, params, body)

    monkeypatch.setattr(type(fake_daftra), "__call__", refuse)
    found = details(client, sales)
    assert found["balance"] == {"owed": 800, "credit": None}
    assert [invoice["unpaid"] for invoice in found["open_invoices"]] == [800]
