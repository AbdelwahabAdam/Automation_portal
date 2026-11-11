"""The page that lists every package with the products inside it."""

from datetime import datetime
from decimal import Decimal

from app.core.text import UAE
from app.jobs.package_report import image_index, notes, packages_of, render, tally
from app.modules.models import Package, PackageItem, Product

WHEN = datetime(2026, 11, 11, 9, 0, tzinfo=UAE)


def catalog(db) -> None:
    """A package whose first product is in order and whose second is not."""
    good = Product(id=1, name="RO System", name_ar="جهاز تنقية", description="سبع مراحل",
                   daftra_id=100, file_id=900, unit_price=Decimal("2000"))
    bare = Product(id=2, name="Filter Set", daftra_id=200, file_id=None, description="",
                   unit_price=Decimal("300"))
    db.add_all([good, bare, Package(id=10, name="باقة الجهاز", code="FLP-001", items=[
        PackageItem(product=good, quantity=1, unit_price=Decimal("2000"), sort_order=1),
        PackageItem(product=bare, quantity=2, unit_price=Decimal("300"), sort_order=2),
    ])])
    db.commit()


def test_a_package_carries_its_products_in_their_own_order(db):
    catalog(db)
    [package] = packages_of(db)
    assert package["code"] == "FLP-001" and package["name"] == "باقة الجهاز"
    assert [item["product"]["name"] for item in package["items"]] == ["RO System", "Filter Set"]
    assert package["items"][1]["quantity"] == 2


def test_an_inactive_package_is_left_out_unless_it_is_asked_for(db):
    catalog(db)
    db.add(Package(id=11, name="باقة قديمة", is_active=False))
    db.commit()
    assert [p["name"] for p in packages_of(db)] == ["باقة الجهاز"]
    assert len(packages_of(db, include_inactive=True)) == 2


def test_an_image_is_read_from_the_file_id_the_work_order_carries(db):
    index = image_index([
        {"id": "100", "name": "RO System", "ProductImageS3": [
            {"id": "900", "default": "1", "file_full_path": "https://x/900.jpg", "file": "900.jpg"}]},
        {"id": "200", "name": "Filter Set", "ProductImageS3": [{"id": "901", "default": "0"}]},
    ])
    assert index[900]["daftra_id"] == 100 and index[900]["is_default"]
    assert index[901]["daftra_id"] == 200


def test_a_row_says_what_looks_wrong_about_it(db):
    catalog(db)
    [package] = packages_of(db)
    first, second = package["items"]
    index = image_index([{"id": "100", "name": "RO System", "ProductImageS3": [
        {"id": "900", "default": "1", "file_full_path": "https://x/900.jpg"}]}])

    assert notes(first, index[900], {}) == []
    # No image of its own, and no description
    assert notes(second, None, {}) == ["لا توجد صورة", "بدون وصف"]
    # The picture belongs to another product in Daftra
    wrong = image_index([{"id": "555", "name": "Cooler", "ProductImageS3": [
        {"id": "900", "default": "1"}]}])
    assert "الصورة تنتمي لمنتج آخر في دفترة: «Cooler»" in notes(first, wrong[900], {})
    # Another product already used this picture
    assert "نفس صورة «Cooler»" in notes(first, index[900], {900: "Cooler"})


def test_a_product_that_is_off_or_unlinked_is_called_out(db):
    db.add_all([Product(id=3, name="Old", is_active=False, description="x", unit_price=Decimal("1"))])
    db.add(Package(id=12, name="باقة", items=[
        PackageItem(product_id=3, quantity=1, unit_price=Decimal("1"))]))
    db.commit()
    [package] = packages_of(db)
    assert notes(package["items"][0], None, {}) == ["منتج غير مفعّل", "غير مرتبط بدفترة", "لا توجد صورة"]


def test_the_page_shows_every_product_and_its_notes(db):
    catalog(db)
    packages = packages_of(db)
    for package in packages:
        package["notes"] = [(item, notes(item, None, {})) for item in package["items"]]
    page = render(packages, {900: b"\xff\xd8pretend-a-jpeg"}, WHEN, "futurelife")

    assert '<html lang="ar" dir="rtl">' in page
    assert "باقة الجهاز" in page and "FLP-001" in page
    assert "جهاز تنقية" in page and "RO System" in page and "سبع مراحل" in page
    assert "Filter Set" in page
    # The picture travels inside the page, so the file still shows it off the server
    assert "data:image/jpeg;base64," in page
    # And the row with nothing to show says so, in the summary as well as in place
    assert "لا صورة" in page and "لا توجد صورة" in page
    assert "2026-11-11 09:00" in page


def test_a_clean_catalog_says_it_has_nothing_to_report(db):
    catalog(db)
    packages = packages_of(db)
    for package in packages:
        package["notes"] = [(item, []) for item in package["items"]]
    assert "لا توجد ملاحظات" in render(packages, {}, WHEN, "futurelife")


def test_an_empty_package_is_named_rather_than_drawn_as_a_table(db):
    db.add(Package(id=13, name="باقة فارغة"))
    db.commit()
    packages = packages_of(db)
    packages[0]["notes"] = []
    page = render(packages, {}, WHEN, "futurelife")
    assert "باقة فارغة: باقة فارغة، لا منتجات داخلها" in page
    assert "لا منتجات داخل هذه الباقة." in page


def test_the_summary_counts_the_kinds_of_note_rather_than_listing_every_row():
    flagged = [
        (None, None, ["لا توجد صورة", "بدون وصف"]),
        (None, None, ["لا توجد صورة"]),
        (None, None, ["الصورة تنتمي لمنتج آخر في دفترة: «Cooler»"]),
        (None, None, ["الصورة تنتمي لمنتج آخر في دفترة: «Filter»"]),
        (None, None, ["نفس صورة «Cooler»"]),
    ]
    counted = tally(flagged)
    # Each note that names a product is one kind, however many names it carries
    assert counted == {"لا توجد صورة": 2, "الصورة تنتمي لمنتج آخر في دفترة": 2,
                       "صورة مكررة بين منتجين": 1, "بدون وصف": 1}
    # What stops an order going out comes first
    assert list(counted)[0] == "لا توجد صورة"
