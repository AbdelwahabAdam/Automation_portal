"""A product sold without a fixed price (بدون سعر ثابت): priced and described on each order line."""

from decimal import Decimal

from app.modules.models import Package, PackageItem, Product, Request

from ... import seed
from ...conftest import auth
from ...seed import create, package_lines, submitted_quotation, submitted_sale


def approve(client, user, request_id, revision=1):
    return client.post(f"/api/review/requests/{request_id}/approve", json={"revision": revision}, headers=auth(user))


def open_product(client, admin, **overrides):
    return client.post("/api/admin/products", headers=auth(admin), json={
        "name": "Custom Work", "unit_price": "999", "description": "أعمال حسب الطلب", "open_price": True, **overrides})


def survey(db) -> Product:
    """An open-price product in the catalog, as the admin page would have made it."""
    product = Product(id=20, name="Site Survey", unit_price=Decimal("0"), daftra_id=820, open_price=True,
                      description="زيارة معاينة للموقع")
    db.add(product)
    db.commit()
    return product


def line(product, price=None, text=None, **more):
    details = {key: value for key, value in (("item_price", price), ("work_description", text)) if value is not None}
    return {"product_id": str(product.id), "name": product.name, "quantity": 1, "group_id": None, "group_name": "",
            "package_id": None, "unit_price": 0, "details": details, **more}


def test_an_open_price_product_has_no_price_and_must_have_its_text(client, admin, fake_daftra):
    made = open_product(client, admin)
    assert made.status_code == 201, made.json()
    assert (made.json()["open_price"], made.json()["unit_price"]) == (True, 0)
    # A service in Daftra like every catalog product, at 0
    [posted] = fake_daftra.posted("/api2/products.json")
    assert posted["Product"]["unit_price"] == 0.0 and posted["Product"]["type"] == 2
    assert open_product(client, admin, name="No Text", description="").status_code == 422


def test_its_line_asks_for_price_and_text_and_the_invoice_carries_them(client, db, fake_daftra, sales, manager):
    seed.catalog(db)
    product = survey(db)
    # Left without either: both asked for, on its own line only
    request_id = create(client, sales, seed.sale_data(order_lines=[line(product)])).json()["id"]
    seed.upload(client, sales, request_id, "payment_proof")
    sent = client.put(f"/api/requests/{request_id}", headers=auth(sales),
                      json={"data": seed.sale_data(order_lines=[line(product)]), "action": "submit"})
    assert sent.status_code == 422
    assert sent.json()["detail"]["errors"]["order_lines"]["lines"]["0"] == {"item_price": "مطلوب", "work_description": "مطلوب"}

    request_id = submitted_sale(client, db, sales, create_work_order="لا", installation_days="", discount_amount="",
                                discount_label="", discount_approved_by="", paid_amount="100",
                                order_lines=[line(product, "350", "معاينة وقياس الموقع")])
    saved = db.get(Request, request_id).data
    assert saved["subtotal_amount"] == 350
    assert approve(client, manager, request_id).status_code == 200
    [invoice] = fake_daftra.posted("/api2/invoices.json")
    assert invoice["InvoiceItem"][0] | {} == {**invoice["InvoiceItem"][0], "product_id": 820, "unit_price": 350.0,
                                             "description": "معاينة وقياس الموقع"}


def test_inside_a_package_it_is_priced_on_the_order_too(client, db, fake_daftra, sales, admin):
    products = seed.catalog(db)
    product = survey(db)
    # The package editor keeps it at 0 whatever is sent
    package = client.post("/api/admin/packages", headers=auth(admin), json={"name": "باقة مع معاينة", "items": [
        {"product_id": products["filter"].id, "quantity": 1, "unit_price": "50"},
        {"product_id": product.id, "quantity": 1, "unit_price": "500", "discount": "10"},
    ]}).json()
    assert [(item["unit_price"], item["discount"], item["open_price"]) for item in package["items"]] == [
        (50.0, 0.0, False), (0.0, 0.0, True)]
    assert package["total"] == 50.0
    picked = next(row for row in client.get("/api/catalog/picker", headers=auth(sales)).json()
                  if row["kind"] == "package" and row["id"] == package["id"])
    assert [item["open_price"] for item in picked["items"]] == [False, True]

    # On the order: its typed price counts, the package's other product keeps the package's
    shared = {"package_quantity": "1", "cooler_color": "أسود"}
    lines = [
        {**line(products["filter"]), "group_id": "g2", "group_name": "باقة مع معاينة", "package_id": package["id"],
         "base_quantity": 1, "details": dict(shared)},
        {**line(product, "200", "معاينة"), "group_id": "g2", "group_name": "باقة مع معاينة",
         "package_id": package["id"], "base_quantity": 1, "details": {**shared, "item_price": "200", "work_description": "معاينة"}},
    ]
    request_id = submitted_quotation(client, db, sales, order_lines=lines, discount_amount="", discount_label="",
                                     discount_approved_by="")
    saved = db.get(Request, request_id).data
    assert [entry["unit_price"] for entry in saved["order_lines"]] == [50.0, 200.0]
    assert saved["subtotal_amount"] == 250
    # The package's fixed-price product is asked for neither
    assert "item_price" not in saved["order_lines"][0]["details"]


def test_a_fixed_price_product_is_not_asked_for_a_price(client, db, sales):
    seed.catalog(db)
    request_id = submitted_sale(client, db, sales, order_lines=package_lines())
    for saved in db.get(Request, request_id).data["order_lines"]:
        assert "item_price" not in saved["details"] and "work_description" not in saved["details"]
    assert db.query(Package).count() == 1 and db.query(PackageItem).count() == 2
