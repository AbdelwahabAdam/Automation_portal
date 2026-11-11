"""Pointing a catalog product at another Daftra product, from the edit drawer.

Changing the number is a correction, so Daftra is what is right: the catalog row takes the new
product's name, price, description, code and picture, and nothing is written to Daftra.
"""

from decimal import Decimal

from tests import seed
from tests.conftest import auth


def service(product_id, name, price, *, images=(), **more):
    """A Daftra service, the kind a catalog product is linked to."""
    return {"id": str(product_id), "name": name, "unit_price": str(price), "description": "", "type": "2",
            "status": "0", "product_code": str(product_id), "ProductImageS3": list(images), **more}


def image(file_id, default="1"):
    return {"id": str(file_id), "default": default, "file_full_path": f"https://files/{file_id}.jpg",
            "file": f"{file_id}.jpg"}


def edit(client, admin, product, **changes):
    body = {"name": product.name, "name_ar": product.name_ar, "description": product.description,
            "unit_price": str(product.unit_price), "is_active": product.is_active,
            "maintenance_group": product.maintenance_group or "", "daftra_id": product.daftra_id, **changes}
    return client.put(f"/api/admin/products/{product.id}", json=body, headers=auth(admin))


def linked(db, fake_daftra, daftra_id=625, file_id=900):
    """A catalog product linked to one Daftra product, with another one to point it at.

    Returns the seeded catalog, whose "filter" is the linked one — a second seed would put the
    same package in twice.
    """
    catalog = seed.catalog(db)
    product = catalog["filter"]
    product.daftra_id, product.file_id, product.product_code = daftra_id, file_id, str(daftra_id)
    db.commit()
    fake_daftra.products = [
        service(daftra_id, product.name, 50, images=[image(file_id)]),
        service(777, "RO Membrane 100 GPD", 180, description="غشاء التناضح العكسي",
                images=[image(901, default="0"), image(902)]),
    ]
    return catalog


def test_the_number_can_be_pointed_at_another_product_and_the_row_follows_it(client, db, admin, fake_daftra):
    product = linked(db, fake_daftra)["filter"]
    response = edit(client, admin, product, daftra_id=777)
    assert response.status_code == 200, response.json()
    saved = response.json()
    assert saved["daftra_id"] == 777
    # Name, price, description and code come from the Daftra product now linked
    assert saved["name"] == "RO Membrane 100 GPD" and saved["unit_price"] == 180
    assert saved["description"] == "غشاء التناضح العكسي" and saved["product_code"] == "777"
    db.expire_all()
    # And so does the picture the work order prints: its default image, not the first one listed
    assert db.get(type(product), product.id).file_id == 902


def test_relinking_writes_nothing_to_daftra(client, db, admin, fake_daftra):
    """Neither product is touched there: the portal is the one being corrected, not Daftra."""
    product = linked(db, fake_daftra)["filter"]
    # The drawer still shows the old name and price; they are passed over, not sent
    assert edit(client, admin, product, daftra_id=777, name="Whatever", unit_price="9").status_code == 200
    assert [call for call in fake_daftra.calls if call[0] in ("PUT", "POST")] == []
    assert fake_daftra.products[1]["name"] == "RO Membrane 100 GPD"


def test_a_number_another_catalog_product_holds_is_refused(client, db, admin, fake_daftra):
    catalog = linked(db, fake_daftra)
    product, other = catalog["filter"], catalog["cooler"]
    other.daftra_id = 777
    db.commit()
    response = edit(client, admin, product, daftra_id=777)
    assert response.status_code == 409 and other.name in response.json()["detail"]
    db.expire_all()
    assert db.get(type(product), product.id).daftra_id == 625


def test_a_number_daftra_does_not_have_is_refused(client, db, admin, fake_daftra):
    product = linked(db, fake_daftra)["filter"]
    response = edit(client, admin, product, daftra_id=404_404)
    assert response.status_code == 422 and "404404" in response.json()["detail"]
    db.expire_all()
    assert db.get(type(product), product.id).daftra_id == 625


def test_a_stock_product_is_not_one_to_link_to(client, db, admin, fake_daftra):
    product = linked(db, fake_daftra)["filter"]
    fake_daftra.products.append(service(888, "Steel tank", 400, type="1"))
    response = edit(client, admin, product, daftra_id=888)
    assert response.status_code == 409 and "مخزون" in response.json()["detail"]


def test_a_name_another_catalog_product_already_uses_stops_the_relink(client, db, admin, fake_daftra):
    catalog = linked(db, fake_daftra)
    product, cooler = catalog["filter"], catalog["cooler"]
    fake_daftra.products[1]["name"] = cooler.name
    response = edit(client, admin, product, daftra_id=777)
    assert response.status_code == 409 and cooler.name in response.json()["detail"]


def test_a_daftra_product_with_no_picture_leaves_the_row_without_one(client, db, admin, fake_daftra):
    """The old picture belongs to the product that is no longer linked, so it does not stay."""
    product = linked(db, fake_daftra)["filter"]
    fake_daftra.products[1]["ProductImageS3"] = []
    assert edit(client, admin, product, daftra_id=777).status_code == 200
    db.expire_all()
    assert db.get(type(product), product.id).file_id is None


def test_leaving_the_number_as_it_is_still_edits_daftra_the_way_it_always_did(client, db, admin, fake_daftra):
    product = linked(db, fake_daftra)["filter"]
    assert edit(client, admin, product, unit_price="55").status_code == 200
    assert [path for method, path, _, _ in fake_daftra.calls if method == "PUT"] == ["/api2/products/625.json"]
    db.expire_all()
    assert db.get(type(product), product.id).unit_price == Decimal("55")


def test_a_product_with_no_link_is_left_alone_when_the_number_is_not_sent(client, db, admin, fake_daftra):
    product = seed.catalog(db)["filter"]
    product.daftra_id = None
    db.commit()
    body = {"name": product.name, "unit_price": "60", "is_active": True}
    assert client.put(f"/api/admin/products/{product.id}", json=body, headers=auth(admin)).status_code == 200
    db.expire_all()
    assert db.get(type(product), product.id).daftra_id is None


# ---------- What the drawer shows beside the number ----------


def test_the_drawer_reads_the_daftra_product_behind_a_number(client, db, admin, fake_daftra):
    linked(db, fake_daftra)
    shown = client.get("/api/admin/daftra-products/777", headers=auth(admin)).json()
    assert shown["name"] == "RO Membrane 100 GPD" and shown["unit_price"] == 180
    assert shown["product_code"] == "777" and shown["is_service"] is True
    assert shown["file_id"] == 902 and shown["image_url"] == "https://files/902.jpg"
    assert shown["linked_to"] is None


def test_it_says_which_catalog_product_already_holds_that_number(client, db, admin, fake_daftra):
    product = linked(db, fake_daftra)["filter"]
    shown = client.get("/api/admin/daftra-products/625", headers=auth(admin)).json()
    assert shown["linked_to"] == {"id": product.id, "name": product.name}


def test_a_number_that_is_not_there_is_said_so_rather_than_shown_empty(client, db, admin, fake_daftra):
    linked(db, fake_daftra)
    response = client.get("/api/admin/daftra-products/404404", headers=auth(admin))
    assert response.status_code == 422 and "404404" in response.json()["detail"]


def test_only_someone_who_keeps_the_catalog_may_read_it(client, db, sales, fake_daftra):
    linked(db, fake_daftra)
    assert client.get("/api/admin/daftra-products/777", headers=auth(sales)).status_code == 403
