"""Manager review, and what approving creates in Daftra (app.review, app.daftra_sync).

These pin the exact payloads sent to Daftra, since they were tuned against the live account.
"""

from datetime import datetime, timedelta, timezone

from app.daftra_sync.invoice import WARRANTY_TERMS_HTML
from app.models import Attachment, Request

from . import seed
from .conftest import auth, make_user
from .test_forms import TODAY
from .test_requests import create, submitted_sale, upload

UAE = timezone(timedelta(hours=4))


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def test_review_queue_shows_sent_requests_only(client, db, sales, manager):
    seed.catalog(db)
    create(client, sales, {"customer_name": "draft only"})
    request_id = submitted_sale(client, db, sales)
    queue = client.get("/api/review/requests", headers=auth(manager)).json()
    assert [r["id"] for r in queue] == [request_id]
    assert queue[0]["created_by_name"] == "Sales One"
    assert client.get("/api/review/requests", headers=auth(sales)).status_code == 403


def test_approving_a_new_sale_creates_everything_in_daftra(client, db, fake_daftra, sales, manager, outbox):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    response = approve(client, manager, request_id)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "approved" and body["reviewed_by_name"] == "Manager One"

    [new_client] = fake_daftra.posted("/api2/clients.json")
    assert new_client == {
        "Client": {"business_name": "عميل تجريبي", "type": 2, "phone1": "0501234567", "address1": "شارع 1",
                   "address2": "فيلا 2", "city": "أبوظبي", "state": "منطقة العين", "country_code": "AE",
                   "default_currency_code": "AED", "category_id": 5, "category": "العين العامره"},
        "le_custom_data_client": {"test": "N + F", "coordinates_text": "24.1787, 55.6045"},
    }
    client_id = int(next(iter(fake_daftra.clients)))

    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert invoice["Invoice"] == {
        "client_id": client_id, "date": TODAY, "draft": 0, "is_offline": 1, "currency_code": "AED", "store_id": 1,
        "branch_id": 1, "sales_person_id": 71, "order_source_id": 16, "po_number": f"PORTAL-{request_id}",
        "adjustment_label": "مبادرة لك ان تشارك", "adjustment_value": -200.0, "html_notes": WARRANTY_TERMS_HTML,
    }
    assert invoice["InvoiceItem"] == [
        {"product_id": 501, "item": "WATER COOLER BLACK 3 T", "unit_price": 2000.0, "quantity": 2, "tax1": 3, "store_id": 1},
        {"product_id": 37, "item": "exchange contract", "unit_price": 800.0, "quantity": 2, "tax1": 3, "store_id": 1,
         "description": "عقد تبديل"},
        {"product_id": 194, "item": "service", "description": "بسم الله", "unit_price": 300.0, "quantity": 2,
         "tax1": 3, "store_id": 1},
    ]
    invoice_id = int(next(iter(fake_daftra.invoices)))

    [payment] = fake_daftra.posted("/api2/invoice_payments.json")
    assert payment == {"InvoicePayment": {
        "invoice_id": invoice_id, "amount": 1000.0, "payment_method": "bank", "treasury_id": 13, "date": TODAY,
        "transaction_id": "TRX-1", "notes": f"PORTAL-{request_id}", "staff_id": 40,
    }}

    [work_order] = fake_daftra.posted("/api2/work_orders.json")
    start = datetime.now(UAE).date()
    fields = work_order["WorkOrder"]
    assert fields["client_id"] == client_id
    assert (fields["start_date"], fields["delivery_date"]) == (start.isoformat(), (start + timedelta(days=20)).isoformat())
    assert fields["title"].startswith("باقة برادة سقيا الخير - 3 صنابير - أسود أبوظبي منطقة العين")
    assert fields["description"].endswith(f"PORTAL-{request_id}")
    assert "■ المسؤول: Manager One" in fields["description"]
    saved = next(iter(fake_daftra.work_orders.values()))
    assert saved["custom"] == {
        "field_30": "لا توجد صورة — أُنشئ من البوابة", "field_32": "سقيا الخير-  اللون الاسود مقاس طبيعي",
        "field_37": "https://maps.google.com/?q=24.17870,55.60451", "field_39": "Sales One",
        "field_44": "اللون الاسود", "field_47": "بسم الله", "field_49": "اللون الاسود مقاس طبيعي",
    }
    assert fake_daftra.invoices[invoice_id]["work_order_id"] == saved["id"]

    request = db.get(Request, request_id)
    db.refresh(request)
    assert request.daftra_invoice_no == f"0{invoice_id}"
    assert request.daftra_receipt_no.startswith("R")
    assert request.daftra_work_order_no.startswith("00100")
    assert request.daftra_error is None
    fields_attached = {a.field for a in db.query(Attachment).filter_by(request_id=request_id)}
    assert {"daftra_invoice", "daftra_receipt", "daftra_work_order"} <= fields_attached
    # The new client is kept in our own list too
    found = client.get("/api/clients/lookup", params={"phone": "0501234567"}, headers=auth(sales)).json()["matches"]
    assert [m["daftra_id"] for m in found] == [client_id]
    assert any(mail["to"] == "sales1@test.local" for mail in outbox)


def test_a_failed_step_is_resumed_without_duplicates(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    fake_daftra.fail_once = "/api2/invoice_payments.json"
    failed = approve(client, manager, request_id)
    assert failed.status_code == 502
    request = db.get(Request, request_id)
    assert request.status == "submitted" and request.daftra_invoice_id and "simulated failure" in request.daftra_error

    assert approve(client, manager, request_id).status_code == 200
    assert len(fake_daftra.posted("/api2/clients.json")) == 1
    assert len(fake_daftra.posted("/api2/invoices.json")) == 1
    assert len(fake_daftra.posted("/api2/invoice_payments.json")) == 1
    assert fake_daftra.posted("/api2/work_orders.json") == []
    db.refresh(request)
    assert request.status == "approved" and request.daftra_error is None


def test_a_lost_invoice_id_is_found_again_by_its_marker(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    fake_daftra.fail_once = "/api2/invoice_payments.json"
    approve(client, manager, request_id)
    request = db.get(Request, request_id)
    request.daftra_invoice_id = None
    db.commit()
    assert approve(client, manager, request_id).status_code == 200
    assert len(fake_daftra.posted("/api2/invoices.json")) == 1


def test_a_product_without_a_daftra_id_stops_the_approval_before_anything_is_sent(client, db, fake_daftra, sales, manager):
    products = seed.catalog(db)
    products["contract"].daftra_id = None
    db.commit()
    request_id = submitted_sale(client, db, sales)
    response = approve(client, manager, request_id)
    assert response.status_code == 409
    assert "exchange contract" in response.json()["detail"]
    assert [c for c in fake_daftra.calls if c[0] != "GET"] == []
    assert db.get(Request, request_id).status == "submitted"


def test_the_salesperson_must_be_linked_to_daftra(client, db, manager):
    seed.catalog(db)
    unlinked = make_user(db, "sales3", pages=["sales.new_request", "sales.my_requests"])
    request_id = submitted_sale(client, db, unlinked)
    response = approve(client, manager, request_id)
    assert response.status_code == 409 and "غير مربوط" in response.json()["detail"]


def test_decision_rules(client, db, sales, manager, admin):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    assert approve(client, manager, request_id, revision=7).status_code == 409
    own = submitted_sale(client, db, make_user(db, "mgr2", manages=["sales"], pages=["sales.new_request"],
                                               daftra_staff_id=71))
    mgr2 = db.query(type(manager)).filter_by(username="mgr2").one()
    assert approve(client, mgr2, own).status_code == 403
    # The system admin may decide on any request, including their own
    assert approve(client, admin, own).status_code == 200
    assert approve(client, admin, own).status_code == 409


def test_returning_and_resubmitting(client, db, sales, manager, outbox):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    short = client.post(f"/api/review/requests/{request_id}/return", json={"revision": 1, "reason": "x"}, headers=auth(manager))
    assert short.status_code == 422
    returned = client.post(f"/api/review/requests/{request_id}/return",
                           json={"revision": 1, "reason": "صحّح رقم الهاتف"}, headers=auth(manager))
    assert returned.json()["status"] == "returned"
    assert "صحّح رقم الهاتف" in outbox[-1]["text"]
    # The owner corrects it, can add and remove files, and sends it again as revision 2
    extra = upload(client, sales, request_id, "inscription_file").json()
    assert client.delete(f"/api/attachments/{extra['id']}", headers=auth(sales)).status_code == 204
    again = client.put(f"/api/requests/{request_id}", json={"data": seed.sale_data(), "action": "submit"}, headers=auth(sales))
    assert again.json()["revision"] == 2
    history = client.get(f"/api/requests/{request_id}/history", headers=auth(manager)).json()
    assert [e["kind"] for e in history] == ["created", "submitted", "returned", "resubmitted"]


def test_contract_renewal(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=1)
    request_id = create(client, sales, seed.renewal_data(), form_type="contract_renewal").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    sent = client.put(f"/api/requests/{request_id}", json={"data": seed.renewal_data(), "action": "submit"}, headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    assert approve(client, manager, request_id).status_code == 200
    assert fake_daftra.clients[4053]["category_id"] == 5
    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert invoice["Invoice"]["client_id"] == 4053
    assert invoice["Invoice"]["html_notes"] == WARRANTY_TERMS_HTML
    assert invoice["InvoiceItem"] == [{
        "product_id": 37, "item": "exchange contract", "description": "تجديد عقد الصيانه لمده عام مع تبديل فلاتر كل ثلاث اشهر",
        "unit_price": 1680.0, "quantity": 1, "tax1": 3, "store_id": 1,
    }]
    assert len(fake_daftra.posted("/api2/invoice_payments.json")) == 1


def test_renewal_for_an_unknown_client_is_refused(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    data = seed.renewal_data(client_code="", phone="0501111111")
    request_id = create(client, sales, data, form_type="contract_renewal").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(sales))
    response = approve(client, manager, request_id)
    assert response.status_code == 409 and "لعميل موجود فقط" in response.json()["detail"]
    assert fake_daftra.posted("/api2/invoices.json") == []


def balance_data(invoice_id, paid="500"):
    return {"request_date": TODAY, "phone": "0509999999", "client_code": "4089", "customer_name": "عميل قديم",
            "invoice": str(invoice_id), "paid_amount": paid, "payment_method": "نقدًا", "treasury": "9",
            "collector_name": "Sales One", "payment_date": TODAY, "payment_reference": "SND-1"}


def test_balance_payment(client, db, fake_daftra, sales, manager):
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999")
    invoice_id = fake_daftra.add_invoice(4053, total=5000, paid=1000)
    request_id = create(client, sales, balance_data(invoice_id), form_type="balance_payment").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    too_much = client.put(f"/api/requests/{request_id}", json={"data": balance_data(invoice_id, "4500"), "action": "submit"},
                          headers=auth(sales))
    assert too_much.status_code == 422
    assert "4,000.00" in too_much.json()["detail"]["errors"]["paid_amount"]
    sent = client.put(f"/api/requests/{request_id}", json={"data": balance_data(invoice_id), "action": "submit"}, headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    assert sent.json()["data"]["invoice_name"].startswith(f"0{invoice_id} — 18/10/2026 — المتبقي 4,000")
    assert approve(client, manager, request_id).status_code == 200
    [payment] = fake_daftra.posted("/api2/invoice_payments.json")
    assert payment["InvoicePayment"]["invoice_id"] == invoice_id
    assert payment["InvoicePayment"]["payment_method"] == "cash"
    assert payment["InvoicePayment"]["amount"] == 500.0
    assert fake_daftra.posted("/api2/invoices.json") == []


def test_maintenance(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    data = {"request_date": TODAY, "order_source": "12", "phone": "0502222222", "customer_name": "عميل صيانة",
            "category": "5", "area": "منطقة العين", "emirate": "أبوظبي", "coordinates": "24.1, 55.6",
            "devices": ["فلتر RO VIB"], "service": "تبديل فلاتر", "visit_date": TODAY,
            "order_lines": [{"product_id": "3", "name": "RO .PP 10", "quantity": 2, "details": {}}],
            "paid_amount": "100", "payment_method": "تحويل بنكي", "treasury": "13", "payment_date": TODAY}
    request_id = create(client, sales, data, form_type="maintenance").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    assert approve(client, manager, request_id).status_code == 200
    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert invoice["InvoiceItem"] == [{"product_id": 625, "item": "RO .PP 10", "unit_price": 50.0, "quantity": 2,
                                       "tax1": 3, "store_id": 1}]
    assert invoice["Invoice"]["notes"] == f"الأجهزة: فلتر RO VIB\nالخدمة: تبديل فلاتر\nتاريخ الزيارة: {'/'.join(reversed(TODAY.split('-')))}"
    assert invoice["Invoice"]["order_source_id"] == 12
    assert invoice["Invoice"]["html_notes"] == WARRANTY_TERMS_HTML


def test_an_unexpected_fault_midway_keeps_what_daftra_created(client, db, fake_daftra, sales, manager, monkeypatch):
    from app import daftra_sync

    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    real = daftra_sync.invoice.save_receipt_pdf

    def broken(*args, **kwargs):
        raise KeyError("boom")
    monkeypatch.setattr(daftra_sync.invoice, "save_receipt_pdf", broken)
    failed = approve(client, manager, request_id)
    assert failed.status_code == 500 and "boom" in failed.json()["detail"]
    request = db.get(Request, request_id)
    assert request.status == "submitted" and request.daftra_invoice_id and request.daftra_payment_id

    monkeypatch.setattr(daftra_sync.invoice, "save_receipt_pdf", real)
    assert approve(client, manager, request_id).status_code == 200
    assert len(fake_daftra.posted("/api2/invoices.json")) == 1
    assert len(fake_daftra.posted("/api2/invoice_payments.json")) == 1


def test_the_pdfs_saved_on_approval_cannot_be_deleted_by_the_owner(client, db, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    approve(client, manager, request_id)
    invoice_pdf = db.query(Attachment).filter_by(request_id=request_id, field="daftra_invoice").one()
    request = db.get(Request, request_id)
    # Even if the request were open for corrections again
    request.status = "returned"
    db.commit()
    assert client.delete(f"/api/attachments/{invoice_pdf.id}", headers=auth(sales)).status_code == 409


# The address seed.renewal_data carries, as Daftra keeps one: the city is the emirate, the state the area
RENEWAL_ADDRESS = {"address1": "", "address2": "", "city": "أبوظبي", "state": "منطقة العين", "country_code": "AE"}


def client_updates(fake, client_id=4053):
    """Every save Daftra was asked to make on that client, in order."""
    return [body for method, path, _, body in fake.calls
            if method == "PUT" and path == f"/api2/clients/{client_id}.json"]


def renewal_request(client, db, sales, **overrides):
    """A contract renewal for the existing client 4053, sent for review."""
    data = seed.renewal_data(**overrides)
    request_id = create(client, sales, data, form_type="contract_renewal").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    return request_id


def test_the_client_is_left_alone_when_daftra_already_has_all_of_it(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    # Daftra already has this client in the category the form picked, with the same address and coordinates
    fake_daftra.add_client(4053, "0509999999", category_id=5,
                           custom={"test": "N + F", "coordinates_text": "24.1, 55.6"},
                           address=RENEWAL_ADDRESS)
    request_id = renewal_request(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    assert client_updates(fake_daftra) == []


def test_a_client_whose_required_fields_are_empty_is_still_given_its_category(client, db, fake_daftra, sales, manager):
    """Daftra refuses any save that leaves اسم الجهاز and Coordinates empty, so they go with every one."""
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=1)
    request_id = renewal_request(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    saves = client_updates(fake_daftra)
    assert len(saves) == 1
    assert saves[0]["le_custom_data_client"] == {"test": "N + F", "coordinates_text": "24.1, 55.6"}
    # This client had no address of its own, so the request's goes there rather than in the spare block
    assert saves[0]["Client"] == {"category_id": 5, "category": "العين العامره", **RENEWAL_ADDRESS,
                                  "business_name": "Existing", "first_name": "", "last_name": ""}
    assert fake_daftra.clients[4053]["category_id"] == 5


def test_the_client_keeps_its_name_when_its_category_changes(client, db, fake_daftra, sales, manager):
    """Daftra blanks a name that a save leaves out, so the one it has is sent back with the category."""
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", name="مؤسسة الواحة لتجارة المياه", category_id=1,
                           custom={"test": "N + F", "coordinates_text": "24.1, 55.6"})
    request_id = renewal_request(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    assert fake_daftra.clients[4053]["category_id"] == 5
    assert fake_daftra.clients[4053]["business_name"] == "مؤسسة الواحة لتجارة المياه"


def test_the_clients_own_device_is_kept_while_its_coordinates_follow_the_request(client, db, fake_daftra, sales, manager):
    """اسم الجهاز is not on the form, so what Daftra holds stands; the الإحداثيات are, so they win."""
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=1,
                           custom={"test": "جهاز العميل الحقيقي", "coordinates_text": "25.0000, 55.0000"})
    request_id = renewal_request(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    assert fake_daftra.clients[4053]["custom"] == {"test": "جهاز العميل الحقيقي", "coordinates_text": "24.1, 55.6"}


def test_a_second_address_goes_into_the_spare_block_and_leaves_the_first_alone(client, db, fake_daftra, sales, manager):
    """Daftra's API can write the client's own address and one more, so a new one takes that slot."""
    seed.catalog(db)
    seed.existing_client(db)
    home = {"address1": "شارع الشيخ زايد", "address2": "12", "city": "دبي", "state": "الخوانيج", "country_code": "AE"}
    fake_daftra.add_client(4053, "0509999999", category_id=5, address=home,
                           custom={"test": "N + F", "coordinates_text": "24.1, 55.6"})
    request_id = renewal_request(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    saved = fake_daftra.clients[4053]
    # The address it already had is untouched
    assert {key: saved[key] for key in home} == home
    assert saved["active_secondary_address"] == 1
    assert saved["secondary_city"] == "أبوظبي" and saved["secondary_state"] == "منطقة العين"


def test_the_location_link_of_the_request_is_put_on_the_client(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=5,
                           custom={"test": "N + F", "coordinates_text": "24.1, 55.6"})
    link = "https://maps.app.goo.gl/NEWLOCATION1"
    request_id = renewal_request(client, db, sales, location_url=link, coordinates="24.1, 55.6")
    assert approve(client, manager, request_id).status_code == 200
    assert fake_daftra.clients[4053]["link"] == link
    # The name is not lost to a save that is only about the link
    assert fake_daftra.clients[4053]["business_name"] == "Existing"


def test_a_request_without_coordinates_says_so_instead_of_failing_in_daftra(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=1)
    request_id = renewal_request(client, db, sales)
    # As an old request submitted before the form asked for them would be
    request = db.get(Request, request_id)
    request.data = {**request.data, "coordinates": ""}
    db.commit()
    response = approve(client, manager, request_id)
    assert response.status_code == 409 and "الإحداثيات" in response.json()["detail"]
