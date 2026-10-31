"""A new catalog product in Daftra, so it can go on an invoice as soon as it is saved."""

from sqlalchemy.orm import Session

from ...core.errors import Conflict, ExternalFailure
from ...integrations import daftra
from . import repo
from .models import Product


def place_in_daftra(db: Session, product: Product):
    """Links the product to Daftra's one of that name, adding it there if there is none, and says
    nothing was saved if Daftra fails. Finding it first means saving again after a failure part
    way does not add a second one."""
    try:
        named = daftra.products_named(product.name)
        if len(named) > 1:
            numbers = "، ".join(str(row["id"]) for row in named)
            raise Conflict(f"يوجد في دفترة أكثر من منتج بهذا الاسم ({numbers}). غيّر الاسم أو عالج التكرار في دفترة.")
        if named:
            source = named[0]
        else:
            # A service with no stock tracked, like every product the catalog is linked to. The
            # tax is not on the product: the invoice's lines carry it.
            added = daftra.create("products.json", {"Product": {
                "name": product.name, "type": daftra.PRODUCT_SERVICE, "track_stock": 0,
                "unit_price": float(product.unit_price), "description": product.description,
            }})
            source = daftra.get(f"products/{added}.json")["data"]["Product"]
    except daftra.DaftraError:
        raise ExternalFailure("تعذر إنشاء المنتج في دفترة، فلم يُحفظ. حاول مرة أخرى.")
    daftra_id = int(source["id"])
    taken = repo.product_with_daftra_id(db, daftra_id)
    if taken is not None:
        raise Conflict(f"منتج دفترة رقم {daftra_id} مربوط بمنتج آخر: «{taken.name}»")
    product.daftra_id = daftra_id
    product.product_code = source.get("product_code") or ""
