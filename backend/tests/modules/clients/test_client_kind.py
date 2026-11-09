"""نوع العميل and الجنس: read from Daftra into our client list, filled in by the search, and a
change made on a form put back on the client in Daftra when the request is approved."""

from app.modules.clients import client_rows
from app.modules.models import Client

from ... import seed
from ...conftest import auth
from ...seed import create, upload


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def test_the_sync_reads_them_as_the_forms_write_them():
    base = {"phone1": "0501111111", "business_name": "X"}
    rows = client_rows([
        {**base, "id": "1", "type": "3", "gender": "2"},
        {**base, "id": "2", "type": "2", "gender": "1"},
        # A code the forms do not offer, or none
        {**base, "id": "3", "type": "9", "gender": ""},
        {**base, "id": "4"},
    ])
    assert [(row["customer_type"], row["gender"]) for row in rows] == [
        ("تجاري", "أنثى"), ("فرد", "ذكر"), ("", ""), ("", "")]


def test_the_search_fills_them_in(client, db, sales):
    found = seed.existing_client(db)
    found.customer_type, found.gender = "تجاري", "أنثى"
    db.commit()
    [match] = client.get("/api/clients/lookup", params={"phone": "0509999999"}, headers=auth(sales)).json()["matches"]
    assert (match["customer_type"], match["gender"]) == ("تجاري", "أنثى")


def test_a_change_on_the_form_goes_back_to_daftra_and_our_copy(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    # Daftra has them as an individual, a man
    fake_daftra.add_client(4053, "0509999999", category_id=1, gender="1")
    fake_daftra.clients[4053]["type"] = "2"
    data = {**seed.renewal_data(), "customer_type": "تجاري", "gender": "أنثى"}
    request_id = create(client, sales, data, form_type="contract_renewal").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    sent = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(sales))
    assert sent.status_code == 200, sent.json()
    assert approve(client, manager, request_id).status_code == 200

    [put] = [body for method, path, _, body in fake_daftra.calls if method == "PUT" and path == "/api2/clients/4053.json"]
    assert (put["Client"]["type"], put["Client"]["gender"]) == (3, 2)
    assert (str(fake_daftra.clients[4053]["type"]), str(fake_daftra.clients[4053]["gender"])) == ("3", "2")
    db.expire_all()
    local = db.query(Client).filter_by(daftra_id=4053).one()
    assert (local.customer_type, local.gender) == ("تجاري", "أنثى")


def test_left_empty_they_change_nothing(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", category_id=5, gender="1")
    fake_daftra.clients[4053]["type"] = "3"
    data = {**seed.renewal_data(), "customer_type": "", "gender": ""}
    request_id = create(client, sales, data, form_type="contract_renewal").json()["id"]
    upload(client, sales, request_id, "payment_proof")
    client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"}, headers=auth(sales))
    assert approve(client, manager, request_id).status_code == 200
    for method, path, _, body in fake_daftra.calls:
        if method == "PUT" and path == "/api2/clients/4053.json":
            assert "type" not in body["Client"] and "gender" not in body["Client"]
    # Our copy now says what Daftra does
    db.expire_all()
    local = db.query(Client).filter_by(daftra_id=4053).one()
    assert (local.customer_type, local.gender) == ("تجاري", "ذكر")
