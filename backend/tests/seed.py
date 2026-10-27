"""Catalog, client and request data the request and review tests start from."""

from decimal import Decimal

from sqlalchemy import text

from app.models import Address, Client, ClientCategory, Package, PackageItem, Product

from .test_forms import PACKAGE, TODAY, new_sale


def catalog(db) -> dict:
    """The two products and the package of tests.test_forms, with the same ids and prices."""
    # file_id: its image in Daftra, which the work order's صورة المنتج carries
    cooler = Product(id=1, name="WATER COOLER BLACK 3 T", unit_price=Decimal("1000"), daftra_id=501, file_id=7809)
    contract = Product(id=2, name="exchange contract", unit_price=Decimal("1200"), daftra_id=37,
                       description="عقد تبديل")
    filter_ = Product(id=3, name="RO .PP 10", unit_price=Decimal("50"), daftra_id=625, maintenance_group="الفلاتر")
    package = Package(id=10, name=PACKAGE, items=[
        PackageItem(product=cooler, quantity=1, unit_price=Decimal("2000"), sort_order=1),
        PackageItem(product=contract, quantity=1, unit_price=Decimal("800"), sort_order=2),
    ])
    db.add_all([cooler, contract, filter_, package,
                ClientCategory(id=5, name="العين العامره", emirate="أبوظبي", area="منطقة العين")])
    db.commit()
    # Rows added later get ids after these
    for table in ("products", "packages"):
        db.execute(text(f"SELECT setval('{table}_id_seq', (SELECT max(id) FROM {table}))"))
    db.commit()
    return {"cooler": cooler, "contract": contract, "filter": filter_, "package": package}


def existing_client(db, daftra_id=4053, phone="0509999999", code="004089") -> Client:
    client = Client(daftra_id=daftra_id, client_code=code, customer_name="عميل قديم", phone=phone,
                    addresses=[Address(emirate="دبي", area="مدينة دبي", street="الشارع", is_default=True)])
    db.add(client)
    db.commit()
    return client


def sale_data(**overrides) -> dict:
    return new_sale(**overrides)


def renewal_data(**overrides) -> dict:
    data = {"request_date": TODAY, "order_source": "16", "phone": "0509999999", "client_code": "4089",
            "customer_name": "عميل قديم", "category": "5", "area": "منطقة العين", "emirate": "أبوظبي",
            "location_url": "https://www.google.com/maps?q=24.100000,55.600000", "coordinates": "24.100000, 55.600000",
            "cooler_type": "سقيا", "subtotal_amount": "1680", "discount_amount": "",
            "paid_amount": "1680", "payment_method": "تحويل بنكي", "treasury": "13", "payment_date": TODAY,
            "payment_reference": "TRX-9"}
    data.update(overrides)
    return data
