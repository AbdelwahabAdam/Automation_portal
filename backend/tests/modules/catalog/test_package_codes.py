"""The كود a package is listed and searched by (FLP-045).

The catalog's import hands these out by position; a package added on the باقات page takes the next
free one, so it is not left with a dash in the list.
"""

from app.modules.catalog.service import next_package_code
from app.modules.models import Package

from ... import seed
from ...conftest import auth


def add_package(client, admin, name):
    return client.post("/api/admin/packages", headers=auth(admin), json={
        "name": name, "items": [{"product_id": 1, "quantity": 1, "unit_price": "100"}]}).json()


def test_a_new_package_takes_the_next_code_after_the_highest(client, db, admin):
    seed.catalog(db)
    db.add_all([
        Package(id=45, code="FLP-045", name="باقة من الاستيراد"),
        # A code written by hand in another shape is passed over rather than counted
        Package(id=46, code="باقة خاصة", name="باقة بكود مكتوب"),
    ])
    db.commit()
    assert add_package(client, admin, "باقة جديدة")["code"] == "FLP-046"
    assert add_package(client, admin, "باقة أخرى")["code"] == "FLP-047"


def test_the_first_package_of_an_empty_catalog_starts_the_numbering(db):
    assert next_package_code(db) == "FLP-001"


def test_the_number_outgrows_its_three_digits(db):
    db.add(Package(id=999, code="FLP-999", name="الباقة الأخيرة"))
    db.commit()
    assert next_package_code(db) == "FLP-1000"
