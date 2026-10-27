"""The «مصادر الطلب» admin page: Daftra's order sources, and adding one there."""

from app.models import AuditLog

from .conftest import auth


def test_only_admins_see_and_add_order_sources(client, sales, manager):
    for user in (sales, manager):
        assert client.get("/api/admin/order-sources", headers=auth(user)).status_code == 403
        assert client.post("/api/admin/order-sources", json={"name": "X"}, headers=auth(user)).status_code == 403


def test_the_page_lists_inactive_sources_too(client, admin):
    rows = client.get("/api/admin/order-sources", headers=auth(admin)).json()
    assert [(r["id"], r["active"]) for r in rows] == [(3, False), (12, True), (16, True)]


def test_a_new_source_is_added_in_daftra_and_offered_on_the_forms(client, db, admin, sales, fake_daftra):
    # The forms' list is cached; adding must not wait for it to run out
    assert [s["id"] for s in client.get("/api/daftra/order_sources", headers=auth(sales)).json()] == [12, 16]
    response = client.post("/api/admin/order-sources", json={"name": "  Website   - جديد "}, headers=auth(admin))
    assert response.status_code == 201
    created = response.json()
    assert created == {"id": 17, "name": "Website - جديد", "active": True, "display_order": 3}
    method, path, _, body = fake_daftra.calls[-2]
    assert (method, path) == ("POST", "/v2/api/entity/order_source")
    assert body == {"name": "Website - جديد", "status": 1, "display_order": 3, "branch_id": 1}
    assert [s["name"] for s in client.get("/api/daftra/order_sources", headers=auth(sales)).json()] == [
        "water", "Sales-جديد", "Website - جديد"]
    entry = db.query(AuditLog).filter_by(action="order_source.create").one()
    assert (entry.username, entry.entity_id, entry.entity_label) == ("admin1", 17, "Website - جديد")


def test_a_name_already_in_daftra_is_refused(client, admin, fake_daftra):
    # Same name but for spacing, case and punctuation; and one that exists but is switched off
    taken = client.post("/api/admin/order-sources", json={"name": "sales - جديد"}, headers=auth(admin))
    assert taken.status_code == 409 and "Sales-جديد" in taken.json()["detail"]
    off = client.post("/api/admin/order-sources", json={"name": "OLD"}, headers=auth(admin))
    assert off.status_code == 409 and "غير مفعّل" in off.json()["detail"]
    assert client.post("/api/admin/order-sources", json={"name": " "}, headers=auth(admin)).status_code == 422
    assert not any(call[0] == "POST" for call in fake_daftra.calls)


def test_daftra_refusing_the_new_source_is_reported(client, admin, fake_daftra):
    # Daftra answers without the new source's id
    original = fake_daftra.create_order_source
    fake_daftra.create_order_source = lambda params, body: {"message": "no"}
    try:
        response = client.post("/api/admin/order-sources", json={"name": "Expo"}, headers=auth(admin))
    finally:
        fake_daftra.create_order_source = original
    assert response.status_code == 502 and "تعذر إضافة المصدر" in response.json()["detail"]


def test_a_source_is_turned_off_and_on_in_daftra(client, db, admin, sales, fake_daftra):
    response = client.put("/api/admin/order-sources/16", json={"active": False}, headers=auth(admin))
    assert response.status_code == 200 and response.json()["active"] is False
    # The id goes in the body too, or Daftra adds a copy instead of editing; every field is sent
    method, path, _, body = next(call for call in fake_daftra.calls if call[0] == "PUT")
    assert (method, path) == ("PUT", "/v2/api/entity/order_source/16")
    assert body == {"id": 16, "name": "Sales-جديد", "status": 0, "display_order": 2, "branch_id": 1}
    assert len(fake_daftra.order_sources) == 3
    # The forms stop offering it at once
    assert [s["id"] for s in client.get("/api/daftra/order_sources", headers=auth(sales)).json()] == [12]
    assert client.put("/api/admin/order-sources/16", json={"active": True}, headers=auth(admin)).json()["active"] is True
    assert [s["id"] for s in client.get("/api/daftra/order_sources", headers=auth(sales)).json()] == [12, 16]
    entries = db.query(AuditLog).filter_by(action="order_source.update").order_by(AuditLog.id).all()
    assert [(e.before, e.after) for e in entries] == [({"active": True}, {"active": False}), ({"active": False}, {"active": True})]
    assert client.put("/api/admin/order-sources/99", json={"active": True}, headers=auth(admin)).status_code == 404
    assert client.put("/api/admin/order-sources/16", json={"active": True}, headers=auth(sales)).status_code == 403


def test_daftra_saving_the_change_as_a_copy_is_reported(client, admin, fake_daftra):
    # Daftra answering with another id means it added a copy, not changed this one
    fake_daftra.update_order_source = lambda source_id, params, body: {"message": "ok", "id": 99}
    response = client.put("/api/admin/order-sources/16", json={"active": False}, headers=auth(admin))
    assert response.status_code == 502 and "99" in response.json()["detail"]
