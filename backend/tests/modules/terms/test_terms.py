"""الشروط والأحكام: versioned texts, the one each package prints, and what the invoice prints."""

from decimal import Decimal

from app.modules.models import AuditLog, Package, PackageItem, Request
from app.modules.terms import as_html, chosen_for

from ... import seed
from ...conftest import auth
from ...seed import submitted_quotation, submitted_sale

TERMS = "/api/admin/terms"


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def new_term(client, admin, name="شروط الضمان", version=1, body="شروط الضمان\n\n1. سنة واحدة"):
    return client.post(TERMS, json={"name": name, "version": version, "body": body}, headers=auth(admin))


def give(client, admin, package_id, term_id):
    return client.put(f"{TERMS}/packages/{package_id}", json={"term_id": term_id}, headers=auth(admin))


def test_a_term_is_a_version_that_is_never_changed(client, db, admin, sales):
    first = new_term(client, admin)
    assert first.status_code == 201
    assert first.json()["label"] == "شروط الضمان — الإصدار 1"
    # The same name and version again is refused; a new version is made beside it
    assert new_term(client, admin, body="غير ذلك").status_code == 409
    assert new_term(client, admin, version=2, body="شروط الضمان\n\n1. سنتان").status_code == 201
    listed = client.get(TERMS, headers=auth(admin)).json()
    assert [(t["version"], t["assigned"], t["printed"]) for t in listed] == [(2, 0, 0), (1, 0, 0)]
    # There is no way to change one: only add and delete
    assert client.put(f"{TERMS}/{first.json()['id']}", json={}, headers=auth(admin)).status_code == 405
    assert db.query(AuditLog).filter_by(action="terms.create").count() == 2
    # Only the catalog's keepers reach it
    assert client.get(TERMS, headers=auth(sales)).status_code == 403


def test_the_text_prints_as_bold_paragraphs():
    assert as_html("شروط\n\n1. <سنة>\n• أ") == (
        "<p><b>شروط</b></p><p><b><br></b></p><p><b>1. &lt;سنة&gt;</b></p><p><b>• أ</b></p>")


def test_a_package_is_given_a_term_or_none(client, db, admin):
    seed.catalog(db)
    term = new_term(client, admin).json()["id"]
    assert give(client, admin, 10, term).json() == {"package_id": 10, "term_id": term}
    assert client.get(f"{TERMS}/packages", headers=auth(admin)).json() == {"10": term}
    assert [t["assigned"] for t in client.get(TERMS, headers=auth(admin)).json()] == [1]
    assert give(client, admin, 10, 999).status_code == 422
    assert give(client, admin, 999, term).status_code == 404
    # Given: it stays
    assert client.delete(f"{TERMS}/{term}", headers=auth(admin)).status_code == 409
    assert give(client, admin, 10, None).json()["term_id"] is None
    assert client.get(f"{TERMS}/packages", headers=auth(admin)).json() == {}
    logged = db.query(AuditLog).filter_by(action="terms.package").all()
    assert [(entry.before, entry.after) for entry in logged] == [
        ({"term_id": None}, {"term_id": term}), ({"term_id": term}, {"term_id": None})]
    assert client.delete(f"{TERMS}/{term}", headers=auth(admin)).status_code == 204


def test_an_invoice_prints_its_packages_term(client, db, fake_daftra, admin, sales, manager):
    seed.catalog(db)
    term = new_term(client, admin).json()
    give(client, admin, 10, term["id"])
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    assert approve(client, manager, request_id).status_code == 200
    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert invoice["Invoice"]["html_notes"] == "<p><b>شروط الضمان</b></p><p><b><br></b></p><p><b>1. سنة واحدة</b></p>"
    request = db.get(Request, request_id)
    assert (request.printed_terms_id, request.printed_terms) == (term["id"], "شروط الضمان — الإصدار 1")
    shown = client.get(f"/api/requests/{request_id}", headers=auth(sales)).json()
    assert shown["printed_terms"] == "شروط الضمان — الإصدار 1"
    # Printed: it stays, even once no package has it
    give(client, admin, 10, None)
    refused = client.delete(f"{TERMS}/{term['id']}", headers=auth(admin))
    assert refused.status_code == 409 and "فواتير" in refused.json()["detail"]


def test_a_quotation_prints_it_too(client, db, fake_daftra, admin, sales, manager):
    seed.catalog(db)
    term = new_term(client, admin).json()["id"]
    give(client, admin, 10, term)
    request_id = submitted_quotation(client, db, sales)
    assert approve(client, manager, request_id).status_code == 200
    [estimate] = fake_daftra.posted("/api2/estimates.json")
    assert estimate["Invoice"]["html_notes"].startswith("<p><b>شروط الضمان</b></p>")
    assert db.get(Request, request_id).printed_terms_id == term


def test_without_terms_on_its_packages_an_invoice_prints_none(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="")
    assert approve(client, manager, request_id).status_code == 200
    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert "html_notes" not in invoice["Invoice"]
    assert db.get(Request, request_id).printed_terms is None


def test_the_first_package_added_that_has_terms_decides(client, db, admin):
    products = seed.catalog(db)
    for package_id in (11, 12):
        db.add(Package(id=package_id, name=f"باقة {package_id}", items=[
            PackageItem(product=products["filter"], quantity=1, unit_price=Decimal("50"), sort_order=1)]))
    db.commit()
    older, newer = (new_term(client, admin, version=v).json()["id"] for v in (1, 2))
    give(client, admin, 10, older)
    give(client, admin, 12, newer)
    # 11 has none, so it never stands in the way; 12 was added before 10
    lines = {"order_lines": [{"product_id": "3"}, {"package_id": "11"}, {"package_id": 12}, {"package_id": 12},
                             {"package_id": 10}]}
    assert chosen_for(db, lines).id == newer
    assert chosen_for(db, {"order_lines": [{"package_id": 10}, {"package_id": 12}]}).id == older
    assert chosen_for(db, {"order_lines": [{"package_id": 11}, {"product_id": "3"}]}) is None
    assert chosen_for(db, {}) is None
