"""The data and helpers the tests start from: the catalog, a client, a form's values,
and building a request through the API.

It is the one place for these, so a test file never imports another test file.
"""

from decimal import Decimal

from sqlalchemy import text

from app.core.text import uae_today
from app.modules.models import Address, Client, ClientCategory, Package, PackageItem, Product

from .conftest import auth



def catalog(db) -> dict:
    """The two products and the package of tests.test_forms, with the same ids and prices."""
    # file_id: its image in Daftra, which the work order's صورة المنتج carries
    cooler = Product(id=1, name="WATER COOLER BLACK 3 T", unit_price=Decimal("1000"), daftra_id=501, file_id=7809)
    contract = Product(id=2, name="exchange contract", unit_price=Decimal("1200"), daftra_id=37,
                       description="عقد تبديل")
    filter_ = Product(id=3, name="RO .PP 10", unit_price=Decimal("50"), daftra_id=625, maintenance_group="الفلاتر")
    # What اعمال اضافية (قسم الفنيات) offers: a service with a price, and «أخرى» priced on the line
    water = Product(id=4, name="Water Connection Service", unit_price=Decimal("6"), daftra_id=212,
                    description="Water  extension", maintenance_group="الخدمات")
    other = Product(id=5, name="service", unit_price=Decimal("300"), daftra_id=194, maintenance_group="الخدمات")
    package = Package(id=10, name=PACKAGE, items=[
        PackageItem(product=cooler, quantity=1, unit_price=Decimal("2000"), sort_order=1),
        PackageItem(product=contract, quantity=1, unit_price=Decimal("800"), sort_order=2),
    ])
    db.add_all([cooler, contract, filter_, water, other, package,
                ClientCategory(id=5, name="العين العامره", emirate="أبوظبي", area="منطقة العين")])
    db.commit()
    # Rows added later get ids after these
    for table in ("products", "packages"):
        db.execute(text(f"SELECT setval('{table}_id_seq', (SELECT max(id) FROM {table}))"))
    db.commit()
    return {"cooler": cooler, "contract": contract, "filter": filter_, "water": water, "other": other,
            "package": package}


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

# ---------- What a form is filled in with ----------

PACKAGE = "باقة برادة سقيا الخير - 3 صنابير - أسود"

PRODUCTS = {
    "1": {"id": 1, "name": "WATER COOLER BLACK 3 T", "price": 1000, "maintenance_group": None, "daftra_id": 501},
    "2": {"id": 2, "name": "exchange contract", "price": 1200, "maintenance_group": None, "daftra_id": 37},
    "3": {"id": 3, "name": "RO .PP 10", "price": 50, "maintenance_group": "الفلاتر", "daftra_id": 625},
    # اعمال اضافية offers these two by their Daftra id; «أخرى» (194) is priced on the line
    "4": {"id": 4, "name": "Water Connection Service", "price": 6, "maintenance_group": "الخدمات", "daftra_id": 212},
    "5": {"id": 5, "name": "service", "price": 300, "maintenance_group": "الخدمات", "daftra_id": 194},
}

PACKAGE_PRICES = {("10", "1"): 2000.0, ("10", "2"): 800.0}

LISTS = {"daftra_order_source": {16: "Sales-جديد"}, "daftra_treasury": {13: "ADIB NEW CURRENT", 9: "خزينه المكتب"},
         "daftra_client_category": {5: "العين العامره"}}

# What the portal calls today is the UAE's day, which is not the machine's when it runs behind UTC+4
TODAY = uae_today().isoformat()

def package_lines(quantity=2, **details):
    shared = {"package_quantity": str(quantity), "cooler_color": "أسود", "cover_color": "الاسود مقاس طبيعي",
              "inscription": "بسم الله", "inscription_price": "300", **details}
    return [
        {"product_id": "1", "name": "WATER COOLER BLACK 3 T", "quantity": quantity, "base_quantity": 1, "group_id": "g1",
         "group_name": PACKAGE, "package_id": 10, "unit_price": 1, "details": dict(shared)},
        {"product_id": "2", "name": "exchange contract", "quantity": quantity, "base_quantity": 1, "group_id": "g1",
         "group_name": PACKAGE, "package_id": 10, "unit_price": 1, "details": dict(shared)},
    ]

def new_sale(**overrides):
    data = {
        "request_date": TODAY, "order_source": "16", "phone": "0501234567", "customer_name": "عميل تجريبي",
        "customer_type": "فرد", "gender": "ذكر",
        "category": "5", "area": "منطقة العين", "emirate": "أبوظبي", "street": "شارع 1", "house": "فيلا 2",
        "location_url": "https://www.google.com/maps?q=24.178700,55.604510", "coordinates": "24.178700, 55.604510",
        "order_lines": package_lines(), "discount_amount": "200", "discount_approved_by": "Manager One",
        "discount_label": "مبادرة لك ان تشارك", "paid_amount": "1000", "remaining_due_date": TODAY,
        "payment_method": "تحويل بنكي", "treasury": "13", "payment_date": TODAY, "payment_reference": "TRX-1",
        "create_work_order": "نعم", "installation_days": "20",
    }
    data.update(overrides)
    return data

def quotation(**overrides):
    """طلب عرض سعر: the same order lines as a sale, and nothing paid."""
    data = {
        "request_date": TODAY, "order_source": "16", "phone": "0501234567", "customer_name": "جهة تجريبية",
        "customer_type": "تجاري", "gender": "ذكر",
        "category": "5", "area": "منطقة العين", "emirate": "أبوظبي", "street": "شارع 1", "house": "فيلا 2",
        "location_url": "https://www.google.com/maps?q=24.178700,55.604510", "coordinates": "24.178700, 55.604510",
        "order_lines": package_lines(), "discount_amount": "200", "discount_approved_by": "Manager One",
        "discount_label": "مبادرة لك ان تشارك", "payment_method": "تحويل بنكي",
    }
    data.update(overrides)
    return data


# ---------- Building a request through the API ----------

def create(client, user, data, action="draft", form_type="new_sale"):
    return client.post("/api/requests", json={"form_type": form_type, "data": data, "action": action}, headers=auth(user))

def upload(client, user, request_id, field, name="proof.jpg", content=b"image-bytes"):
    return client.post(f"/api/requests/{request_id}/attachments", params={"field": field, "filename": name},
                       content=content, headers=auth(user))

def submitted_quotation(client, db, user, **overrides) -> int:
    """A quotation submitted for review; returns its id. It needs no attachments."""
    data = quotation(**overrides)
    request_id = create(client, user, data, form_type="quotation").json()["id"]
    response = client.put(f"/api/requests/{request_id}", json={"data": data, "action": "submit"},
                          headers=auth(user))
    assert response.status_code == 200, response.json()
    return request_id


def submitted_sale(client, db, user, **overrides) -> int:
    """A new sale request with its files, submitted for review; returns its id."""
    request_id = create(client, user, sale_data(**overrides)).json()["id"]
    assert upload(client, user, request_id, "payment_proof").status_code == 201
    assert upload(client, user, request_id, "design_image").status_code == 201
    response = client.put(f"/api/requests/{request_id}", json={"data": sale_data(**overrides), "action": "submit"},
                          headers=auth(user))
    assert response.status_code == 200, response.json()
    return request_id
