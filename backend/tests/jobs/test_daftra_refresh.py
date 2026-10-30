"""The «المزامنة مع دفترة» admin page: refreshing the linked products and the clients from Daftra."""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import daftra_refresh, import_clients
from app.models import AuditLog, Client, Product, SyncRun

from .conftest import auth


@pytest.fixture(autouse=True)
def runs_inline(monkeypatch):
    """The page starts a background thread; here the runs happen before the request returns."""
    class Inline:
        def __init__(self, target, args=(), daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(daftra_refresh.threading, "Thread", Inline)


def daftra_product(product_id, name, price=None, deactivate="0"):
    return {"id": str(product_id), "name": name, "unit_price": price, "deactivate": deactivate}


def test_only_admins_can_sync(client, sales, manager):
    for user in (sales, manager):
        assert client.get("/api/admin/daftra-sync", headers=auth(user)).status_code == 403
        assert client.post("/api/admin/daftra-sync", json={"kinds": ["products"]}, headers=auth(user)).status_code == 403


def test_linked_products_take_name_price_and_active_from_daftra(client, db, admin, fake_daftra):
    db.add_all([
        Product(name="Cooler", unit_price=Decimal("1500"), daftra_id=10),
        Product(name="Filter", unit_price=Decimal("50"), daftra_id=11),
        Product(name="Gone", unit_price=Decimal("5"), daftra_id=12),
        Product(name="Taken name", unit_price=Decimal("7"), daftra_id=13),
        Product(name="Clash", unit_price=Decimal("9"), daftra_id=14),
        Product(name="Local only", unit_price=Decimal("1")),
    ])
    db.commit()
    fake_daftra.products = [
        daftra_product(10, "  WATER  COOLER  ", "1700"),      # renamed (spaces squashed) and repriced
        daftra_product(11, "Filter", None, deactivate="1"),    # no price in Daftra: ours is kept; deactivated
        daftra_product(14, "Taken name", "9"),                 # its Daftra name belongs to another product here
        daftra_product(13, "Taken name", "7"),                 # unchanged
        daftra_product(99, "Only in Daftra", "100"),           # never added
    ]
    response = client.post("/api/admin/daftra-sync", json={"kinds": ["products"]}, headers=auth(admin))
    assert response.status_code == 202

    db.expire_all()
    products = {p.daftra_id: p for p in db.query(Product)}
    assert (products[10].name, products[10].unit_price, products[10].is_active) == ("WATER COOLER", Decimal("1700"), True)
    assert (products[11].name, products[11].unit_price, products[11].is_active) == ("Filter", Decimal("50"), False)
    assert products[12].is_active and products[14].name == "Clash"
    assert db.query(Product).count() == 6

    status = client.get("/api/admin/daftra-sync", headers=auth(admin)).json()
    last = next(k for k in status["kinds"] if k["key"] == "products")["last"]
    assert last["status"] == "done" and last["started_by"] == "Admin One"
    summary = last["summary"]
    assert summary["linked"] == 5 and summary["unchanged"] == 1
    assert {c["name"]: c["after"] for c in summary["changed"]} == {
        "WATER COOLER": {"name": "WATER COOLER", "unit_price": 1700.0}, "Filter": {"is_active": False}}
    assert [m["daftra_id"] for m in summary["missing"]] == [12]
    assert [s["name"] for s in summary["skipped"]] == ["Clash"]
    # Each changed product is in the activity log, with what it was before
    entries = db.query(AuditLog).filter_by(action="product.daftra_sync").order_by(AuditLog.id).all()
    assert [(e.entity_label, e.before) for e in entries] == [
        ("WATER COOLER", {"name": "Cooler", "unit_price": 1500.0}), ("Filter", {"is_active": True})]
    assert db.query(AuditLog).filter_by(action="daftra.sync").one().username == "admin1"


def test_clients_are_rebuilt_from_daftra(client, db, admin, fake_daftra):
    db.add(Client(daftra_id=500, client_code="000500", customer_name="Left Daftra", phone="0505555555"))
    db.commit()
    fake_daftra.add_client(1, "0501111111", name="A")
    fake_daftra.add_client(2, "", name="No phone")
    client.post("/api/admin/daftra-sync", json={"kinds": ["clients"]}, headers=auth(admin))
    db.expire_all()
    assert [c.customer_name for c in db.query(Client)] == ["A"]
    last = next(k for k in client.get("/api/admin/daftra-sync", headers=auth(admin)).json()["kinds"] if k["key"] == "clients")["last"]
    assert last["summary"] == {"daftra_clients": 2, "kept": 1, "without_phone": 1, "addresses": 1, "added": 1, "removed": 1}


def test_a_failed_sync_changes_nothing_and_says_why(client, db, admin, fake_daftra):
    db.add(Product(name="Cooler", unit_price=Decimal("1500"), daftra_id=10))
    db.commit()
    fake_daftra.fail_once = "/api2/products.json"
    client.post("/api/admin/daftra-sync", json={"kinds": ["products", "clients"]}, headers=auth(admin))
    runs = {run.kind: run for run in db.query(SyncRun)}
    assert runs["products"].status == "failed" and "simulated failure" in runs["products"].error
    # The other part still ran
    assert runs["clients"].status == "done"
    assert db.query(Product).one().unit_price == Decimal("1500")


def test_one_sync_at_a_time_and_a_dead_one_is_closed(client, db, admin):
    running = SyncRun(kind="clients", status="running", started_by_name="x")
    db.add(running)
    db.commit()
    assert client.post("/api/admin/daftra-sync", json={"kinds": ["products"]}, headers=auth(admin)).status_code == 409
    # Still "running" long after it started: the server was restarted mid-run
    running.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()
    status = client.get("/api/admin/daftra-sync", headers=auth(admin)).json()
    clients = next(k for k in status["kinds"] if k["key"] == "clients")
    assert clients["busy"] is None and clients["last"]["status"] == "failed"
    assert client.post("/api/admin/daftra-sync", json={"kinds": ["products"]}, headers=auth(admin)).status_code == 202
    assert client.post("/api/admin/daftra-sync", json={"kinds": ["nope"]}, headers=auth(admin)).status_code == 422


def test_the_nightly_client_job_is_recorded_as_a_run(db, fake_daftra, monkeypatch, capsys):
    fake_daftra.add_client(1, "0501111111", name="A")
    monkeypatch.setattr(sys, "argv", ["import"])
    import_clients.main()
    run = db.query(SyncRun).one()
    assert (run.kind, run.status, run.started_by_name, run.started_by_id) == ("clients", "done", "المزامنة الليلية", None)
    assert "1 of 1 clients kept" in capsys.readouterr().out
