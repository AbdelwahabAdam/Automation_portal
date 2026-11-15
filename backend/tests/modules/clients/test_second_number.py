"""A client's رقم مسؤول اخر (phone2) is not who they are, and a request on a client of another name
is warned about. Request 162 (2026-11-15): حمد السناني, a new client, was put on محمد سعيد سهيل
(004162), whose second number was حمد's own — found when the returned request was reopened."""

from app.modules.clients import same_person
from app.modules.models import Client, Request

from ... import seed
from ...conftest import auth
from ...seed import create, sale_data, submitted_sale


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def test_a_client_is_found_by_their_own_number_only(client, db, sales):
    seed.existing_client(db)  # 0509999999, and 0507777777 as their second number
    by_second = client.get("/api/clients/lookup", params={"phone": "0507777777"}, headers=auth(sales)).json()
    assert by_second == {"matches": []}
    by_own = client.get("/api/clients/lookup", params={"phone": "0509999999"}, headers=auth(sales)).json()
    assert [m["client_code"] for m in by_own["matches"]] == ["004089"]


def test_a_new_client_whose_number_is_another_clients_second_one_is_made_a_client(client, db, fake_daftra,
                                                                                  sales, manager):
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", name="عميل قديم", category_id=5)
    fake_daftra.clients[4053]["phone2"] = "0507777777"
    request_id = submitted_sale(client, db, sales, phone="0507777777", customer_name="حمد السناني",
                                create_work_order="لا", installation_days="")
    assert approve(client, manager, request_id).status_code == 200

    [made] = fake_daftra.posted("/api2/clients.json")
    assert (made["Client"]["business_name"], made["Client"]["phone1"]) == ("حمد السناني", "0507777777")
    request = db.get(Request, request_id)
    assert request.daftra_client_id != 4053
    # The other client is left as they were
    assert fake_daftra.clients[4053]["phone2"] == "0507777777"
    assert db.query(Client).filter_by(daftra_id=4053).one().phone2 == "0507777777"


def test_a_request_on_a_client_of_another_name_carries_a_warning(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    seed.existing_client(db)

    def warning(request_id):
        response = client.get(f"/api/requests/{request_id}", headers=auth(manager))
        assert response.status_code == 200
        return response.json()["client_warning"]

    # Someone else's client code, as request 162 had
    by_code = create(client, sales, sale_data(client_code="4089", customer_name="حمد يوسف محمد السناني")).json()["id"]
    said = warning(by_code)
    assert "كود العميل 004089" in said and "«عميل قديم»" in said and "«حمد يوسف محمد السناني»" in said
    # Someone else's own number, with no code
    by_phone = create(client, sales, sale_data(phone="0509999999", customer_name="حمد السناني")).json()["id"]
    assert warning(by_phone).startswith("رقم الهاتف 0509999999")
    # Their own name, however it is spelled, and a new client: nothing to say
    same = create(client, sales, sale_data(client_code="4089", customer_name="عميل  قديم جدا")).json()["id"]
    assert warning(same) is None
    assert warning(create(client, sales, sale_data()).json()["id"]) is None


def test_an_approved_request_carries_no_warning(client, db, fake_daftra, sales, manager):
    """Once approved it is in Daftra under whichever client it went to; there is nothing left to decide."""
    seed.catalog(db)
    seed.existing_client(db)
    fake_daftra.add_client(4053, "0509999999", name="عميل قديم", category_id=5)
    request_id = submitted_sale(client, db, sales, client_code="4089", phone="0509999999",
                                customer_name="حمد السناني", create_work_order="لا", installation_days="")
    assert client.get(f"/api/requests/{request_id}", headers=auth(manager)).json()["client_warning"]
    assert approve(client, manager, request_id).status_code == 200
    assert client.get(f"/api/requests/{request_id}", headers=auth(manager)).json()["client_warning"] is None


def test_same_person():
    assert not same_person("حمد يوسف محمد السناني", "محمد سعيد سهيل")
    assert not same_person("فهد سعيد العطر", "محمد سعيد العطر")
    assert same_person("محمد سعيد", "محمد سعيد سهيل")
    assert same_person("حمد السنانى", "حمد السناني")
    assert same_person("عبدالله احمد", "عبد الله احمد")
    assert same_person("مُحمّد علي", "محمد علي")
    assert same_person("Qaiser nadeem", "QAISER NADEEM Mohd Latif")
    # Nothing to compare is no difference
    assert same_person("", "محمد") and same_person("محمد", "")
