"""The command-line imports that fill the catalog and the client list."""

import json
import sys
from decimal import Decimal

from openpyxl import Workbook

from app import import_clients, import_maintenance_items
from app.models import Client, Product


def test_maintenance_items_are_added_or_marked(db, tmp_path, monkeypatch):
    # Another product already carries the Daftra id the import would give "RO .PP 10"
    db.add_all([Product(name="RO .PP 10", unit_price=Decimal("50")), Product(name="RO CTO 10", unit_price=Decimal("31")),
                Product(name="old pp filter", unit_price=Decimal("1"), daftra_id=625)])
    db.commit()
    book = Workbook()
    sheet = book.active
    for row in ([], [], [], ["التصنيف", "اسم الفاتورة", "اسم البوابة"],
                ["الفلاتر", "RO .PP 10", "فلتر PP"], ["الفلاتر", "RO  CTO 10", "فلتر كربون"]):
        sheet.append(row)
    path = tmp_path / "items.xlsx"
    book.save(path)
    monkeypatch.setattr(sys, "argv", ["import", str(path)])
    import_maintenance_items.main()
    db.expire_all()
    added = db.query(Product).filter_by(name="RO .PP 10").one()
    assert added.maintenance_group == "الفلاتر" and added.unit_price == 50 and added.daftra_id is None
    marked = db.query(Product).filter_by(name="RO CTO 10").one()
    assert marked.maintenance_group == "الفلاتر" and marked.unit_price == Decimal("31") and marked.daftra_id == 627
    assert marked.name_ar == "فلتر كربون"


def test_clients_import_keeps_clients_with_a_phone(db, tmp_path, monkeypatch):
    export = {"data": [
        {"Client": {"id": "1", "client_number": "000001", "business_name": "A", "phone1": "+971 50 111 1111",
                    "phone2": "0501111111", "city": "ابو ظبى", "state": "الشامخة", "address1": "st", "link": "https://m",
                    "default_address": {"id": 9}, "addresses": [{"id": 9, "city": "دبى", "state": "", "address1": "x"}]}},
        {"Client": {"id": "2", "client_number": "000002", "first_name": "B", "last_name": "C", "phone1": "",
                    "phone2": "0522222222", "city": "العين"}},
        {"Client": {"id": "3", "client_number": "000003", "business_name": "No phone"}},
    ]}
    path = tmp_path / "clients.json"
    path.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["import", str(path)])
    import_clients.main()
    clients = {c.client_code: c for c in db.query(Client)}
    assert set(clients) == {"000001", "000002"}
    first, second = clients["000001"], clients["000002"]
    assert (first.phone, first.phone2) == ("0501111111", "")
    assert [(a.emirate, a.street, a.link, a.is_default) for a in first.addresses] == [("دبي", "x", "https://m", True)]
    assert second.customer_name == "B C" and second.phone == "0522222222"
    # With no neighbourhood of its own, العين gives the region it is in, which the form offers
    assert (second.addresses[0].emirate, second.addresses[0].area) == ("أبوظبي", "منطقة العين")


def test_the_import_brings_back_an_address_the_portal_put_in_the_spare_block(db, tmp_path, monkeypatch):
    """Daftra does not list its second address block among a client's «addresses», so it is read
    from the client itself — otherwise an address added through the portal is lost on the next run."""
    export = {"data": [
        {"Client": {"id": "1", "client_number": "000001", "business_name": "A", "phone1": "0501111111",
                    "city": "دبى", "state": "الخوانيج", "address1": "st",
                    "active_secondary_address": "1", "secondary_city": "عجمان",
                    "secondary_state": "مدينة عجمان", "secondary_address1": "شارع الاتحاد"}},
    ]}
    path = tmp_path / "clients.json"
    path.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["import", str(path)])
    import_clients.main()
    client = db.query(Client).one()
    assert [(a.emirate, a.area, a.street) for a in client.addresses] == [
        ("دبي", "الخوانيج", "st"), ("عجمان", "مدينة عجمان", "شارع الاتحاد")]


def test_create_user_from_the_command_line(db, monkeypatch, capsys):
    import pytest

    from app import create_user
    from app.models import User
    monkeypatch.setattr(sys, "argv", ["create_user", "Boss", "long-password", "--admin", "--name", "Big Boss",
                                      "--email", "Boss@Example.com"])
    create_user.main()
    user = db.query(User).filter_by(username="boss").one()
    assert user.is_admin and user.email == "boss@example.com" and user.full_name == "Big Boss"
    for argv in (["create_user", "a@b.c", "long-password"], ["create_user", "ok.name", "short"],
                 ["create_user", "ok.name", "long-password", "--email", "nope"]):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            create_user.main()
    assert db.query(User).count() == 1
