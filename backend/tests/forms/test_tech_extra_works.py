"""What اعمال اضافية (قسم الفنيات) needs from the catalog (alembic 0022)."""

import importlib.util
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from app.forms.tech_extra_works.definition import OTHER_WORK_DAFTRA_ID, TECH_SERVICE_DAFTRA_IDS, TECH_SERVICE_PRICES
from app.modules.models import Product

# Loaded by file, because a migration is not meant to be imported by name
_spec = importlib.util.spec_from_file_location(
    "migration_0022",
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0022_tech_work_product.py",
)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_every_work_has_its_price_but_other_which_is_priced_on_its_line():
    assert set(TECH_SERVICE_PRICES) == set(TECH_SERVICE_DAFTRA_IDS) - {OTHER_WORK_DAFTRA_ID}


def test_the_migration_adds_the_work_a_catalog_is_missing(db):
    db.execute(text(migration.ADD_PRODUCT))
    db.commit()
    product = db.query(Product).filter_by(daftra_id=433).one()
    assert (product.name, product.unit_price, product.product_code, product.is_active) == (
        "interlocking paving Removel $ Breaking Service", Decimal("10.00"), "2016", True)


def test_the_migration_leaves_a_catalog_that_has_it_alone(db):
    db.add(Product(name="interlocking paving Removel $ Breaking Service", daftra_id=433, unit_price=Decimal("25")))
    db.commit()
    db.execute(text(migration.ADD_PRODUCT))
    db.commit()
    assert db.query(Product).filter_by(daftra_id=433).one().unit_price == Decimal("25.00")
