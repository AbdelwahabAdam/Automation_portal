"""The admin pages: users, roles, the catalog, the audit log and the mail test."""

import csv
import io

from app.modules.models import AuditLog, Package, Request, User

from .. import seed
from ..conftest import auth, make_user, may_fill


def test_admin_pages_are_for_admins_only(client, sales, manager):
    for user in (sales, manager):
        assert client.get("/api/admin/users", headers=auth(user)).status_code == 403
        assert client.get("/api/admin/products", headers=auth(user)).status_code == 403


def test_creating_a_user_sends_the_invitation(client, db, admin, outbox):
    role = client.post("/api/admin/roles", json={
        "name": "مبيعات", "permissions": ["form.new_sale.submit", "admin.users", "nope"],
    }, headers=auth(admin)).json()
    # The admin-only keys and unknown ones cannot be put in a role
    assert role["permissions"] == ["form.new_sale.submit"]
    created = client.post("/api/admin/users", json={
        "username": "New.User", "email": "New@Example.com ", "full_name": "New User", "role_ids": [role["id"]],
        "daftra_staff_id": 71,
    }, headers=auth(admin))
    assert created.status_code == 201
    body = created.json()
    assert body["email_sent"] is True and body["link"] is None
    assert body["user"]["username"] == "new.user" and body["user"]["email"] == "new@example.com"
    assert body["user"]["has_password"] is False
    assert outbox[-1]["to"] == "new@example.com"
    duplicate = client.post("/api/admin/users", json={"username": "new.user", "email": "x@y.z", "full_name": "x"},
                            headers=auth(admin))
    assert duplicate.status_code == 409
    bad = client.post("/api/admin/users", json={"username": "a@b", "email": "x@y.z", "full_name": "x"}, headers=auth(admin))
    assert bad.status_code == 422


def test_an_admin_cannot_lock_themselves_out(client, admin):
    body = {"email": admin.email, "full_name": "x", "role_ids": [], "is_admin": False, "is_active": True}
    assert client.put(f"/api/admin/users/{admin.id}", json=body, headers=auth(admin)).status_code == 409
    assert client.delete(f"/api/admin/users/{admin.id}", headers=auth(admin)).status_code == 409


def test_a_user_with_requests_is_stopped_not_deleted(client, db, admin, sales):
    db.add(Request(form_type="new_sale", data={}, status="draft", created_by_id=sales.id))
    db.commit()
    assert client.delete(f"/api/admin/users/{sales.id}", headers=auth(admin)).status_code == 409
    other = make_user(db, "temp")
    assert client.delete(f"/api/admin/users/{other.id}", headers=auth(admin)).status_code == 204
    assert db.query(User).filter_by(id=other.id).count() == 0


def test_roles(client, db, admin, sales):
    roles = client.get("/api/admin/roles", headers=auth(admin)).json()
    [role] = roles
    assert role["user_count"] == 1
    assert client.delete(f"/api/admin/roles/{role['id']}", headers=auth(admin)).status_code == 409
    taken = client.post("/api/admin/roles", json={"name": role["name"].upper(), "permissions": []},
                        headers=auth(admin))
    assert taken.status_code == 409
    # The two tabs of الأدوار والصلاحيات: a row per form with its three keys, then the admin pages
    offered = client.get("/api/admin/permissions", headers=auth(admin)).json()
    assert offered["what"] == {"submit": "تعبئة", "view": "عرض", "review": "مراجعة"}
    new_sale = next(row for row in offered["forms"] if row["key"] == "new_sale")
    assert new_sale["keys"] == {"submit": "form.new_sale.submit", "view": "form.new_sale.view",
                               "review": "form.new_sale.review"}
    # Every form is offered, including the hidden ones, and the two admin-only keys are not
    assert len(offered["forms"]) == 19
    assert {p["key"] for p in offered["admin_pages"]}.isdisjoint({"admin.users", "admin.roles"})


def test_products_and_packages(client, db, admin):
    seed.catalog(db)
    products = client.get("/api/admin/products", headers=auth(admin)).json()
    assert {p["name"]: p["package_count"] for p in products} == {
        "exchange contract": 1, "RO .PP 10": 0, "WATER COOLER BLACK 3 T": 1,
        "Water Connection Service": 0, "service": 0}
    new = client.post("/api/admin/products", json={"name": "  New   Filter ", "unit_price": "99.5"},
                      headers=auth(admin)).json()
    assert new["name"] == "New Filter" and new["unit_price"] == 99.5
    assert client.delete("/api/admin/products/1", headers=auth(admin)).status_code == 409

    package = client.post("/api/admin/packages", json={"name": "Test pack", "items": [
        {"product_id": new["id"], "quantity": 2, "unit_price": "100", "price_includes_tax": False, "discount": "10"},
    ]}, headers=auth(admin)).json()
    # 2 x 100, plus 5% tax, minus the line's 10
    assert package["total"] == 200.0
    assert package["code"] == ""
    # A code from the catalog's import stays, though the form no longer has one to send
    db.get(Package, package["id"]).code = "FLP-001"
    db.commit()
    updated = client.put(f"/api/admin/packages/{package['id']}", json={"name": "Test pack", "items": [
        {"product_id": new["id"], "quantity": 3, "unit_price": "100"}, {"product_id": 3, "quantity": 1, "unit_price": "50"},
    ]}, headers=auth(admin)).json()
    assert updated["total"] == 350.0 and len(updated["items"]) == 2
    assert updated["code"] == "FLP-001"
    repeated = client.put(f"/api/admin/packages/{package['id']}", json={"name": "Test pack", "items": [
        {"product_id": 3, "quantity": 1, "unit_price": "50"}, {"product_id": 3, "quantity": 1, "unit_price": "50"},
    ]}, headers=auth(admin))
    assert repeated.status_code == 422
    assert client.delete(f"/api/admin/packages/{package['id']}", headers=auth(admin)).status_code == 204


def new_product(client, admin, **overrides):
    return client.post("/api/admin/products", json={"name": "Sensor", "unit_price": "40", **overrides},
                       headers=auth(admin))


def test_a_new_product_is_created_in_daftra_as_a_service(client, admin, fake_daftra):
    response = new_product(client, admin, description="Motion sensor")
    assert response.status_code == 201
    [posted] = fake_daftra.posted("/api2/products.json")
    assert posted == {"Product": {"name": "Sensor", "type": 2, "track_stock": 0, "unit_price": 40.0,
                                  "description": "Motion sensor"}}
    [in_daftra] = fake_daftra.products
    assert response.json()["daftra_id"] == int(in_daftra["id"])
    assert response.json()["product_code"] == in_daftra["product_code"]


def test_a_product_daftra_already_has_is_linked_not_added_again(client, admin, fake_daftra):
    fake_daftra.products = [
        {"id": "50", "name": "SENSOR", "type": "2", "status": "0", "product_code": "2099"},
        # Neither of these is one to link to: it tracks stock, or it is switched off
        {"id": "51", "name": "Sensor", "type": "1", "status": "0"},
        {"id": "52", "name": "Sensor", "type": "2", "status": "1"},
    ]
    response = new_product(client, admin)
    assert response.json()["daftra_id"] == 50 and response.json()["product_code"] == "2099"
    assert fake_daftra.posted("/api2/products.json") == []


def test_two_products_of_that_name_in_daftra_are_not_guessed_between(client, admin, fake_daftra):
    fake_daftra.products = [{"id": str(id_), "name": "Sensor", "type": "2", "status": "0"} for id_ in (50, 60)]
    response = new_product(client, admin)
    assert response.status_code == 409 and "50" in response.json()["detail"]
    assert client.get("/api/admin/products", headers=auth(admin)).json() == []


def test_a_daftra_product_another_catalog_product_holds_is_refused(client, admin, fake_daftra):
    fake_daftra.products = [{"id": "50", "name": "Sensor", "type": "2", "status": "0"}]
    assert new_product(client, admin).status_code == 201
    assert new_product(client, admin, name="sensor!").status_code == 409


def test_a_product_daftra_could_not_take_is_not_saved(client, admin, fake_daftra):
    fake_daftra.fail_once = "/api2/products.json"
    assert new_product(client, admin).status_code == 502
    assert client.get("/api/admin/products", headers=auth(admin)).json() == []


def test_editing_a_product_leaves_what_came_from_daftra(client, db, admin, fake_daftra):
    products = seed.catalog(db)
    cooler = products["cooler"]
    cooler.product_code, cooler.barcode, cooler.buy_price = "2008", "12345", 900
    cooler.stock_balance, cooler.category, cooler.brand = 3, "برادات", "Future Life"
    db.commit()
    response = client.put(f"/api/admin/products/{cooler.id}", json={"name": cooler.name, "unit_price": "1100"},
                          headers=auth(admin))
    assert response.status_code == 200
    saved = response.json()
    assert saved["unit_price"] == 1100 and saved["daftra_id"] == 501 and saved["product_code"] == "2008"
    assert (saved["barcode"], saved["buy_price"], saved["stock_balance"]) == ("12345", 900, 3)
    assert (saved["category"], saved["brand"]) == ("برادات", "Future Life")
    assert fake_daftra.posted("/api2/products.json") == []


def test_audit_log_filters_and_csv_export(client, db, admin, sales):
    client.post("/api/auth/login", json={"username": "=cmd|' /C calc'!A0", "password": "x"})
    client.post("/api/auth/login", json={"username": "sales1", "password": "secret-pass-1"})
    page = client.get("/api/admin/audit", params={"action": "auth.login"}, headers=auth(admin)).json()
    assert page["total"] == 1 and page["items"][0]["username"] == "sales1"
    exported = client.get("/api/admin/audit/export", headers=auth(admin))
    assert exported.text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(exported.text.lstrip("﻿"))))
    # A value Excel would run as a formula is written as text
    assert any(row[1].startswith("'=") for row in rows[1:])
    assert db.query(AuditLog).filter_by(action="audit.export").count() == 1
    options = client.get("/api/admin/audit/options", headers=auth(admin)).json()
    assert options["actions"]["request.approve"] == "اعتماد طلب"


def test_mail_test_page(client, admin, outbox):
    settings_page = client.get("/api/admin/mail", headers=auth(admin)).json()
    assert settings_page["configured"] is True
    keys = [t["key"] for t in settings_page["templates"]]
    for key in keys:
        preview = client.get(f"/api/admin/mail/preview/{key}", headers=auth(admin)).json()
        assert preview["subject"].startswith("[تجربة]") and "<html" in preview["html"].lower()
    sent = client.post("/api/admin/mail/test", json={"template": keys[0], "to": "me@test.local"}, headers=auth(admin))
    assert sent.status_code == 204 and outbox[-1]["to"] == "me@test.local"
    assert client.get("/api/admin/mail/preview/nope", headers=auth(admin)).status_code == 404


def test_daftra_staff_for_linking_users(client, admin):
    staff = client.get("/api/admin/daftra/staff", headers=auth(admin)).json()
    assert staff == [{"id": 40, "name": "Manager One"}, {"id": 71, "name": "Sales One"}]


def count_queries(client, path, headers):
    from sqlalchemy import event

    from app.core.database import engine
    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        assert client.get(path, headers=headers).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    return len(statements)


def test_lists_load_in_a_fixed_number_of_queries(client, db, admin, sales):
    seed.catalog(db)
    for n in range(8):
        make_user(db, f"extra{n}", permissions=may_fill("new_sale"))
        db.add(Request(form_type="new_sale", data={"customer_name": str(n)}, status="submitted", created_by_id=sales.id))
    db.commit()
    headers = auth(admin)
    for path in ("/api/admin/users", "/api/admin/roles", "/api/admin/packages", "/api/review/requests",
                 "/api/catalog/picker"):
        assert count_queries(client, path, headers) <= 6, path


def test_the_running_version_is_reported_to_admins_only(client, admin, sales, monkeypatch):
    from app.core.config import settings
    for name, value in [("app_version", "1.2.3"), ("app_build", "87"), ("app_commit", "a7c7354"),
                        ("app_built_at", "2026-10-21 19:58")]:
        monkeypatch.setattr(settings, name, value)
    assert client.get("/api/admin/version", headers=auth(sales)).status_code == 403
    assert client.get("/api/admin/version", headers=auth(admin)).json() == {
        "version": "1.2.3", "build": "87", "commit": "a7c7354", "built_at": "2026-10-21 19:58"}
