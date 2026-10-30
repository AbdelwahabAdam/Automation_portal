"""The job runner: what there is to run, that every run is recorded, and the one behaviour
change of phase 5 — an address Daftra refused is no longer wiped overnight."""

import pytest

from app import jobs
from app.integrations import daftra
from app.jobs import runner
from app.jobs.__main__ import main
from app.jobs.models import JobRun
from app.modules import clients
from app.modules.models import Address, Client


def test_every_job_is_listed(capsys):
    assert main(["--list"]) == 0
    printed = capsys.readouterr().out
    for job in jobs.all_jobs():
        assert job.name in printed, f"{job.name} is not listed"


def test_the_jobs_the_sync_page_offers():
    assert sorted(job.name for job in jobs.on_admin_page()) == ["sync_clients", "sync_products"]


def test_an_unknown_job_says_so(capsys):
    assert main(["no_such_job"]) == 2
    assert "No job called" in capsys.readouterr().err


def test_a_run_is_recorded_with_its_summary(db, fake_daftra):
    fake_daftra.add_client(1, "0501111111", name="A")
    run = runner.run_now("sync_clients")
    assert (run.name, run.status) == ("sync_clients", "done")
    assert run.summary["kept"] == 1
    assert run.started_at is not None and run.finished_at is not None
    assert db.query(JobRun).filter_by(name="sync_clients").one().status == "done"


def test_a_failed_run_is_recorded_with_why(db, fake_daftra):
    fake_daftra.fail_once = "/api2/clients.json"
    run = runner.run_now("sync_clients")
    assert run.status == "failed" and "simulated failure" in run.error


def test_a_client_keeps_its_row_and_id_through_a_sync(db, fake_daftra):
    """It used to empty both tables and build them again, so every id changed every night."""
    fake_daftra.add_client(7001, "0501111111", name="A")
    runner.run_now("sync_clients")
    first = db.query(Client).one()
    client_id, address_ids = first.id, sorted(a.id for a in first.addresses)

    runner.run_now("sync_clients")
    db.expire_all()
    again = db.query(Client).one()
    assert again.id == client_id
    assert sorted(a.id for a in again.addresses) == address_ids


def test_an_address_daftra_refused_survives_the_night(db, fake_daftra, monkeypatch):
    """The whole point of the change: the sync keeps it, and offers it to Daftra again."""
    fake_daftra.add_client(7001, "0501111111", name="A",
                           custom={"test": "N + F", "coordinates_text": "25,55"})
    client = Client(daftra_id=7001, client_code="007001", customer_name="A", phone="0501111111")
    client.addresses = [Address(emirate="عجمان", area="مدينة عجمان", street="شارع", house="",
                                in_daftra=False)]
    db.add(client)
    db.commit()

    # Daftra will not take it this time
    def refuse(daftra_id, data):
        raise daftra.DaftraError("HTTP 400: refused")

    monkeypatch.setattr(clients.in_daftra, "save_address", refuse)
    runner.run_now("sync_clients")
    db.expire_all()
    kept = db.query(Address).filter_by(in_daftra=False).one()
    assert (kept.emirate, kept.street) == ("عجمان", "شارع")


def test_an_address_daftra_then_accepts_is_marked_as_taken(db, fake_daftra, monkeypatch):
    fake_daftra.add_client(7001, "0501111111", name="A",
                           custom={"test": "N + F", "coordinates_text": "25,55"})
    client = Client(daftra_id=7001, client_code="007001", customer_name="A", phone="0501111111")
    client.addresses = [Address(emirate="عجمان", area="مدينة عجمان", street="شارع", house="",
                                in_daftra=False)]
    db.add(client)
    db.commit()

    taken = []
    monkeypatch.setattr(clients.in_daftra, "save_address", lambda i, d: taken.append(i))
    held = clients.resend_held_addresses(db)
    assert held == {"resent": 1, "accepted": 1, "still_refused": 0}
    assert taken == [7001]
    db.expire_all()
    assert db.query(Address).one().in_daftra is True


def test_an_address_the_portal_saves_starts_as_not_in_daftra(client, db, sales, fake_daftra, monkeypatch):
    """So that if Daftra refuses it, the nightly sync knows to keep it and try again."""
    from ..conftest import auth

    fake_daftra.add_client(7001, "0501111111", name="A")
    db.add(Client(daftra_id=7001, client_code="007001", customer_name="A", phone="0501111111"))
    db.commit()

    monkeypatch.setattr(clients.in_daftra, "save_address",
                        lambda i, d: (_ for _ in ()).throw(daftra.DaftraError("refused")))
    answer = client.post("/api/clients/7001/addresses", headers=auth(sales),
                         json={"emirate": "عجمان", "area": "مدينة عجمان", "street": "ش", "house": "",
                               "location_url": "", "coordinates": "25,55"})
    assert answer.status_code == 200 and answer.json()["saved_in_daftra"] is False
    db.expire_all()
    assert db.query(Address).one().in_daftra is False


@pytest.mark.parametrize("name", ["sync_clients", "sync_products"])
def test_the_page_and_the_command_line_run_the_same_job(name):
    assert jobs.get(name).run is not None
