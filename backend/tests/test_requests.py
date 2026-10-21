"""A salesperson's requests: drafts, attachments, submitting, and who can see what."""

from app.models import AuditLog, Request

from . import seed
from .conftest import auth, make_user


def create(client, user, data, action="draft", form_type="new_sale"):
    return client.post("/api/requests", json={"form_type": form_type, "data": data, "action": action}, headers=auth(user))


def upload(client, user, request_id, field, name="proof.jpg", content=b"image-bytes"):
    return client.post(f"/api/requests/{request_id}/attachments", params={"field": field, "filename": name},
                       content=content, headers=auth(user))


def submitted_sale(client, db, user, **overrides) -> int:
    """A new sale request with its files, submitted for review; returns its id."""
    request_id = create(client, user, seed.sale_data(**overrides)).json()["id"]
    assert upload(client, user, request_id, "payment_proof").status_code == 201
    assert upload(client, user, request_id, "design_image").status_code == 201
    response = client.put(f"/api/requests/{request_id}", json={"data": seed.sale_data(**overrides), "action": "submit"},
                          headers=auth(user))
    assert response.status_code == 200, response.json()
    return request_id


def test_form_types_list_hides_the_hidden_forms(client, sales):
    types = client.get("/api/form-types", headers=auth(sales)).json()
    shown = {t["key"] for t in types if not t["hidden"]}
    assert shown == {"new_sale", "contract_renewal", "balance_payment", "maintenance"}


def test_draft_then_submit(client, db, sales):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales)
    request = client.get(f"/api/requests/{request_id}", headers=auth(sales)).json()
    assert request["status"] == "submitted" and request["revision"] == 1
    assert request["data"]["total_amount"] == 6000
    assert {a["field"] for a in request["attachments"]} == {"payment_proof", "design_image"}
    # Locked once sent
    again = client.put(f"/api/requests/{request_id}", json={"data": {}, "action": "draft"}, headers=auth(sales))
    assert again.status_code == 409
    history = client.get(f"/api/requests/{request_id}/history", headers=auth(sales)).json()
    assert [event["kind"] for event in history] == ["created", "submitted"]


def test_submit_with_errors_answers_with_them_and_keeps_the_draft(client, db, sales):
    seed.catalog(db)
    request_id = create(client, sales, seed.sale_data()).json()["id"]
    response = client.put(f"/api/requests/{request_id}", json={"data": seed.sale_data(phone=""), "action": "submit"},
                          headers=auth(sales))
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert errors["phone"] == "مطلوب"
    assert errors["payment_proof"] == "أرفق ملفًا واحدًا على الأقل"
    assert db.get(Request, request_id).status == "draft"


def test_hidden_and_unknown_forms_take_no_new_requests(client, sales):
    assert create(client, sales, {}, form_type="quotation").status_code == 409
    assert create(client, sales, {}, form_type="nope").status_code == 404


def test_requests_are_private_to_their_owner(client, db, sales):
    other = make_user(db, "sales2", pages=["sales.new_request"])
    request_id = create(client, sales, {"customer_name": "x"}).json()["id"]
    assert client.get(f"/api/requests/{request_id}", headers=auth(other)).status_code == 404
    assert client.put(f"/api/requests/{request_id}", json={"data": {}, "action": "draft"}, headers=auth(other)).status_code == 404
    assert client.delete(f"/api/requests/{request_id}", headers=auth(other)).status_code == 404
    assert client.get("/api/requests/mine", headers=auth(other)).json() == []


def test_users_without_the_sales_pages_cannot_use_them(client, db):
    outsider = make_user(db, "outsider")
    assert client.get("/api/form-types", headers=auth(outsider)).status_code == 403
    assert client.get("/api/requests/mine", headers=auth(outsider)).status_code == 403


def test_attachments(client, db, sales):
    request_id = create(client, sales, {}).json()["id"]
    assert upload(client, sales, request_id, "not_a_field").status_code == 400
    assert upload(client, sales, request_id, "payment_proof", name="virus.exe").status_code == 400
    assert upload(client, sales, request_id, "payment_proof", content=b"").status_code == 400
    attachment = upload(client, sales, request_id, "payment_proof", name="إيصال.pdf").json()
    assert attachment["filename"] == "إيصال.pdf" and attachment["content_type"] == "application/pdf"
    downloaded = client.get(f"/api/attachments/{attachment['id']}", headers=auth(sales))
    assert downloaded.status_code == 200 and downloaded.content == b"image-bytes"
    other = make_user(db, "sales2", pages=["sales.new_request"])
    assert client.get(f"/api/attachments/{attachment['id']}", headers=auth(other)).status_code == 404
    assert client.delete(f"/api/attachments/{attachment['id']}", headers=auth(sales)).status_code == 204
    assert client.get(f"/api/attachments/{attachment['id']}", headers=auth(sales)).status_code == 404


def test_deleting_a_draft(client, db, sales):
    request_id = create(client, sales, {"customer_name": "x"}).json()["id"]
    assert client.delete(f"/api/requests/{request_id}", headers=auth(sales)).status_code == 204
    assert db.get(Request, request_id) is None
    assert db.query(AuditLog).filter_by(action="request.delete").count() == 1


def test_client_lookup_by_phone_and_code(client, db, sales):
    seed.existing_client(db)
    by_phone = client.get("/api/clients/lookup", params={"phone": "+971 50 999 9999"}, headers=auth(sales)).json()
    assert [m["client_code"] for m in by_phone["matches"]] == ["004089"]
    assert by_phone["matches"][0]["emirate"] == "دبي"
    by_code = client.get("/api/clients/lookup", params={"code": "٤٠٨٩"}, headers=auth(sales)).json()
    assert by_code["matches"][0]["daftra_id"] == 4053
    assert client.get("/api/clients/lookup", params={"phone": "123"}, headers=auth(sales)).json() == {"matches": []}
    assert client.get("/api/clients/lookup", params={"code": "0"}, headers=auth(sales)).json() == {"matches": []}


def test_adding_an_address_to_a_client(client, db, sales):
    seed.existing_client(db)
    added = client.post("/api/clients/4053/addresses", json={"emirate": "عجمان", "area": "مدينة عجمان"},
                        headers=auth(sales))
    assert added.status_code == 200 and added.json()["emirate"] == "عجمان"
    found = client.get("/api/clients/lookup", params={"code": "4089"}, headers=auth(sales)).json()["matches"][0]
    assert len(found["addresses"]) == 2 and found["emirate"] == "عجمان"
    assert client.post("/api/clients/1/addresses", json={}, headers=auth(sales)).status_code == 404


def test_catalog_picker_lists_packages_with_their_prices(client, db, sales):
    seed.catalog(db)
    items = client.get("/api/catalog/picker", headers=auth(sales)).json()
    package = next(item for item in items if item["kind"] == "package")
    assert package["price"] == 2800
    assert [(i["product_id"], i["unit_price"]) for i in package["items"]] == [(1, 2000.0), (2, 800.0)]
    assert {item["name"] for item in items if item["kind"] == "product"} == {"WATER COOLER BLACK 3 T", "exchange contract", "RO .PP 10"}
    products = client.get("/api/products", headers=auth(sales)).json()
    assert [p["name"] for p in products] == ["exchange contract", "RO .PP 10", "WATER COOLER BLACK 3 T"]


def test_daftra_lists_for_the_forms(client, db, sales):
    seed.catalog(db)
    assert client.get("/api/daftra/staff", headers=auth(sales)).json() == ["Manager One", "Sales One"]
    assert [t["id"] for t in client.get("/api/daftra/treasuries", headers=auth(sales)).json()] == [13, 9]
    assert [s["id"] for s in client.get("/api/daftra/order_sources", headers=auth(sales)).json()] == [12, 16]
    categories = client.get("/api/daftra/client_categories", headers=auth(sales)).json()
    assert categories == [{"id": 5, "name": "العين العامره", "emirate": "أبوظبي", "area": "منطقة العين"}]
