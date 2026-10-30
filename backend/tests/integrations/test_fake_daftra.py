"""The fake Daftra account: the switch, what it keeps, the seed, and the guards around it.

The module with the commands is imported as `commands`, because `fake_daftra` is the fixture
that hands a test its own account.
"""

import asyncio

import pytest

from app import main
from app.jobs import fake_daftra as commands
from app.modules import clients as clients_module
from app.core.config import settings
from app.modules.form_engine import TREASURY_BY_METHOD
from app.integrations import daftra
from app.integrations.daftra import fake, live
from app.integrations.daftra.client import _backend
from app.integrations.daftra.fake import FakeDaftra
from app.modules.models import Address, Client

from ..conftest import auth, make_user, may_fill


def test_the_switch_picks_each_side(monkeypatch):
    monkeypatch.setattr(settings, "daftra_fake", True)
    assert _backend() is fake
    monkeypatch.setattr(settings, "daftra_fake", False)
    assert _backend() is live


def test_what_the_fake_holds_survives_a_new_instance(tmp_path):
    """A restart must not forget invoices that requests still point at."""
    store = tmp_path / "fake_daftra.json"
    first = FakeDaftra(store=store, first_id=fake.FIRST_LOCAL_ID, numbered_clients=True)
    first.add_client(900000050, "0501110000", name="عميل")
    invoice_id = first.add_invoice(900000050, 1000.0)

    again = FakeDaftra(store=store, first_id=fake.FIRST_LOCAL_ID, numbered_clients=True)
    assert 900000050 in again.clients
    assert again.invoices[invoice_id]["summary_total"] == "1000.0"
    # And it carries on from the ids already given, so none is ever handed out twice
    assert again._new_id() > invoice_id


def test_a_local_fake_numbers_its_clients_in_six_digits():
    """The forms check رقم العميل is six digits, so a nine-digit id cannot be used as one."""
    account = FakeDaftra(store=None, first_id=fake.FIRST_LOCAL_ID, numbered_clients=True)
    new_id = account.create_client({}, {"Client": {"business_name": "x"}})["id"]
    assert len(account.clients[new_id]["client_number"]) == 6


def test_the_fake_ids_cannot_be_mistaken_for_real_ones():
    assert fake.FIRST_LOCAL_ID > 900000000


def test_an_unknown_call_says_which_one(tmp_path):
    """A local portal shows the manager what the fake does not know; a test fails outright."""
    local = FakeDaftra(store=tmp_path / "f.json")
    with pytest.raises(daftra.DaftraError) as refused:
        local("GET", "/api2/nothing_here.json")
    assert "/api2/nothing_here.json" in str(refused.value)

    with pytest.raises(AssertionError):
        FakeDaftra()("GET", "/api2/nothing_here.json")


def test_seeding_then_a_client_sync_leaves_the_local_clients_as_they_were(db, fake_daftra):
    """The fake is filled from the database, so a sync back out of it changes nothing."""
    client = Client(daftra_id=4100, client_code="004100", customer_name="عميل قائم", phone="0509998877")
    client.addresses = [Address(emirate="دبي", area="الخوانيج 2", street="شارع", house="فيلا", is_default=True)]
    db.add(client)
    db.commit()

    fake_daftra.seed(commands._seed_data(db))
    assert 4100 in fake_daftra.clients

    clients_module.sync_from_daftra(db, daftra.list_clients())
    db.commit()
    db.expire_all()
    again = db.query(Client).filter_by(daftra_id=4100).one()
    assert (again.customer_name, again.phone, again.client_code) == ("عميل قائم", "0509998877", "004100")
    assert [(a.emirate, a.area) for a in again.addresses] == [("دبي", "الخوانيج 2")]


def test_seeding_again_adds_nothing_twice(db, fake_daftra):
    db.add(Client(daftra_id=4200, client_code="004200", customer_name="ثاني", phone="0501112222"))
    db.commit()
    data = commands._seed_data(db)
    assert fake_daftra.seed(data)["clients"] == 1
    assert fake_daftra.seed(data)["clients"] == 0


def test_the_portal_refuses_to_start_with_the_fake_on_and_a_real_version(monkeypatch):
    """On the server every approval would look successful with no invoice behind it."""
    monkeypatch.setattr(settings, "daftra_fake", True)
    monkeypatch.setattr(settings, "app_version", "1.4")

    async def start():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError) as refused:
        asyncio.run(start())
    assert "DAFTRA_FAKE" in str(refused.value)


def test_the_commands_refuse_when_the_fake_is_off(monkeypatch, capsys):
    monkeypatch.setattr(settings, "daftra_fake", False)
    assert commands.main(["calls"]) == 2
    assert "DAFTRA_FAKE is off" in capsys.readouterr().err


def test_fail_once_makes_the_next_call_fail_then_work(fake_daftra):
    """What `fake_daftra fail-once` sets up, so approving again can be tried."""
    fake_daftra.fail_once = "/api2/treasuries.json"
    with pytest.raises(daftra.DaftraError):
        daftra.get("treasuries.json")
    assert daftra.get("treasuries.json")["data"]


def test_me_says_whether_the_fake_is_on(client, db, monkeypatch):
    user = make_user(db, "someone", permissions=may_fill("new_sale"))
    monkeypatch.setattr(settings, "daftra_fake", True)
    assert client.get("/api/auth/me", headers=auth(user)).json()["daftra_fake"] is True
    monkeypatch.setattr(settings, "daftra_fake", False)
    assert client.get("/api/auth/me", headers=auth(user)).json()["daftra_fake"] is False


def test_the_local_treasuries_are_the_ones_the_forms_expect():
    """Submitting checks the treasury id against Daftra's list, so every id a payment method
    maps to must be in the fake's own list."""
    offered = {int(row["id"]) for row in fake.LOCAL_TREASURIES}
    assert set(TREASURY_BY_METHOD.values()) <= offered


def test_seeding_with_nothing_local_adds_a_few_samples(fake_daftra):
    empty = {"clients": [], "products": [], "categories": [], "staff": []}
    assert fake_daftra.seed(empty)["clients"] > 0
    assert fake_daftra.clients


def test_the_kept_calls_do_not_grow_without_end(tmp_path):
    account = FakeDaftra(store=tmp_path / "f.json")
    for _ in range(fake.KEPT_CALLS + 20):
        account("GET", "/api2/treasuries.json")
    assert len(account.calls) <= fake.KEPT_CALLS
