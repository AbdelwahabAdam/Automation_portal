"""طلب بيع - دفع إلكتروني: approving makes the client and invoice and emails it to the client, and
the request waits «بانتظار الدفع» until its work order is made."""

from app.modules.form_engine import get
from app.modules.models import Client, Request

from .. import seed
from ..conftest import auth, make_user, may_fill
from ..seed import TODAY, create

EMAIL = "client@example.com"


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def act(client, user, request_id, action, **values):
    return client.post(f"/api/requests/{request_id}/actions/{action}", json={"values": values}, headers=auth(user))


def online_sale(**overrides) -> dict:
    data = {**seed.new_sale(), "email": EMAIL, "paid_amount": "0", "remaining_due_date": TODAY, **overrides}
    for name in ("create_work_order", "installation_days"):
        data.pop(name, None)
    return data


def submitted(client, user, **overrides) -> int:
    data = online_sale(**overrides)
    request_id = create(client, user, data, form_type="online_sale").json()["id"]
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(user))
    assert sent.status_code == 200, sent.json()
    return request_id


def test_the_form_is_a_sale_with_an_email_nothing_paid_and_no_work_order():
    spec = get("online_sale")
    titles = [section["title"] for section in spec.sections]
    assert "التركيب وأمر الشغل" not in titles and titles[:4] == [s["title"] for s in get("new_sale").sections][:4]
    fields = {field["name"]: field for field in spec.fields()}
    assert fields["email"]["required"] and not fields["email"].get("new_client")
    assert fields["paid_amount"]["default"] == "0" and not fields["paid_amount"].get("positive")
    attachments = next(section for section in spec.sections if section["title"] == "المرفقات")
    assert attachments["fields"] and not any(field["required"] for field in attachments["fields"])
    assert "installation_days" not in fields
    assert [action.key for action in spec.actions] == ["create_work_order", "resend_invoice_email"]


def test_approving_emails_the_invoice_and_waits_for_the_payment(client, db, fake_daftra, sales, manager, outbox):
    seed.catalog(db)
    # No attachments at all: none is required
    request_id = submitted(client, sales)
    approved = approve(client, manager, request_id)
    assert approved.status_code == 200, approved.json()
    assert approved.json()["status"] == "awaiting_payment"

    # The client and invoice, and no payment: nothing was paid
    [new_client] = fake_daftra.posted("/api2/clients.json")
    assert new_client["Client"]["email"] == EMAIL
    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert fake_daftra.posted("/api2/invoice_payments.json") == []
    request = db.get(Request, request_id)
    assert request.daftra_invoice_id and not fake_daftra.posted("/api2/work_orders.json")

    [mail] = [m for m in outbox if m["to"] == EMAIL]
    assert mail["subject"] == f"الفاتورة #{request.daftra_invoice_no} من FUTURE LIFE L.L.C O.P.C"
    assert f"/invoices/preview/{request.daftra_invoice_id}?hash=x" in mail["html"]
    assert "عميل تجريبي" in mail["text"] and "المبلغ المستحق" in mail["text"]
    assert mail["attachments"] and mail["attachments"][0][1] == "application/pdf"
    history = client.get(f"/api/requests/{request_id}/history", headers=auth(sales)).json()
    assert {"invoice_emailed", "approved"} <= {e["kind"] for e in history}
    # The salesperson's own list counts it apart
    assert client.get("/api/requests/mine/counts", headers=auth(sales)).json()["awaiting_payment"] == 1


def test_an_email_that_does_not_go_does_not_stop_the_approval(client, db, fake_daftra, sales, manager, outbox, monkeypatch):
    from app.modules import notifications

    down = {"now": True}
    working = notifications.send

    def send(*args, **kwargs):
        if down["now"]:
            raise notifications.MailError("mail server down")
        return working(*args, **kwargs)
    monkeypatch.setattr(notifications, "send", send)
    seed.catalog(db)
    request_id = submitted(client, sales)
    assert approve(client, manager, request_id).json()["status"] == "awaiting_payment"
    assert not [m for m in outbox if m["to"] == EMAIL]
    # Sent again once it works
    down["now"] = False
    resent = act(client, sales, request_id, "resend_invoice_email")
    assert resent.status_code == 200, resent.json()
    assert [m["to"] for m in outbox] == [EMAIL]


def test_an_existing_clients_email_is_put_on_them(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=5)
    request_id = submitted(client, sales, phone="0509999999", client_code="004089", customer_name="عميل قديم",
                           email="new@example.com")
    assert approve(client, manager, request_id).status_code == 200
    assert fake_daftra.clients[4053]["email"] == "new@example.com"
    db.expire_all()
    assert db.query(Client).filter_by(daftra_id=4053).one().email == "new@example.com"


def test_resending_and_making_the_work_order(client, db, fake_daftra, sales, manager, outbox):
    seed.catalog(db)
    request_id = submitted(client, sales)
    approve(client, manager, request_id)
    sent_before = len([m for m in outbox if m["to"] == EMAIL])

    resent = act(client, sales, request_id, "resend_invoice_email")
    assert resent.status_code == 200 and resent.json()["status"] == "awaiting_payment"
    assert len([m for m in outbox if m["to"] == EMAIL]) == sent_before + 1

    # مدة التركيب is asked for, and checked
    bad = act(client, manager, request_id, "create_work_order", installation_days="0")
    assert bad.status_code == 422 and "installation_days" in bad.json()["detail"]["errors"]
    made = act(client, manager, request_id, "create_work_order", installation_days="15")
    assert made.status_code == 200, made.json()
    assert made.json()["status"] == "approved" and made.json()["daftra_work_order_no"]
    [work_order] = fake_daftra.posted("/api2/work_orders.json")
    assert work_order["WorkOrder"]["delivery_date"] > work_order["WorkOrder"]["start_date"]
    request = db.get(Request, request_id)
    assert request.data["installation_days"] == 15
    kinds = [e["kind"] for e in client.get(f"/api/requests/{request_id}/history", headers=auth(sales)).json()]
    assert "resend_invoice_email" in kinds and "create_work_order" in kinds
    labels = {e["kind"]: e["label"] for e in client.get(f"/api/requests/{request_id}/history", headers=auth(sales)).json()}
    assert labels["create_work_order"] == "إنشاء أمر الشغل"

    # Done: neither is offered any more
    assert act(client, sales, request_id, "resend_invoice_email").status_code == 409


def test_only_its_owner_or_a_reviewer_may_act_on_it(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted(client, sales)
    # Not before approval
    assert act(client, sales, request_id, "resend_invoice_email").status_code == 409
    approve(client, manager, request_id)
    other = make_user(db, "sales2", permissions=may_fill("online_sale"), daftra_staff_id=72)
    assert act(client, other, request_id, "resend_invoice_email").status_code == 404
    assert act(client, sales, request_id, "no_such_action").status_code == 404
