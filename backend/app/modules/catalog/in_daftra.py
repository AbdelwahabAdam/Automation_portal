"""A catalog product's Daftra twin: added when the product is, changed when it is, and deleted
with it when the admin asks for that."""

from sqlalchemy.orm import Session

from ...core.errors import Conflict, ExternalFailure
from ...integrations import daftra
from . import repo
from .models import Product

# What an edit in the portal also changes in Daftra. The rest (Arabic name, maintenance group,
# active) is the portal's own: Daftra keeps active in two flags, and which one its screens use
# is not known.
SENT_TO_DAFTRA = {"name": "name", "unit_price": "unit_price", "description": "description"}


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


def edit_in_daftra(product: Product, changed: dict):
    """Sends the name, price and description just changed to the Daftra product it is linked to,
    so the next sync does not put the old ones back. Raises, and so nothing is saved, if Daftra
    refuses or cannot be reached.

    Only a service is changed. Daftra empties a product's average cost (average_price) on any
    edit through the API, which a service does not use but a stock product's cost does: those are
    changed in Daftra itself, and the sync brings the change here.

    brand_id is sent back as it was: the edit empties that too (the brand's name stays).
    """
    fields = {daftra_name: changed[ours] for ours, daftra_name in SENT_TO_DAFTRA.items() if ours in changed}
    if product.daftra_id is None or not fields:
        return
    try:
        source = daftra.get(f"products/{product.daftra_id}.json")["data"]["Product"]
    except daftra.NotFound:
        raise Conflict(f"منتج دفترة رقم {product.daftra_id} المربوط به لم يعد موجودًا في دفترة، فلم يُحفظ التعديل.")
    except daftra.DaftraError:
        raise ExternalFailure("تعذر الوصول إلى المنتج في دفترة، فلم يُحفظ التعديل. حاول مرة أخرى.")
    if str(source.get("type")) != str(daftra.PRODUCT_SERVICE):
        raise Conflict(f"المنتج مربوط بمنتج مخزون في دفترة (رقم {product.daftra_id})، فلا يُعدَّل اسمه أو سعره أو "
                       "وصفه من البوابة. عدّله في دفترة ثم اضغط «مزامنة من دفترة».")
    try:
        if "name" in fields:
            others = [row for row in daftra.products_named(product.name) if int(row["id"]) != product.daftra_id]
            if others:
                numbers = "، ".join(str(row["id"]) for row in others)
                raise Conflict(f"يوجد في دفترة منتج آخر بهذا الاسم ({numbers})، فلم يُحفظ التعديل.")
        if source.get("brand_id"):
            fields["brand_id"] = source["brand_id"]
        if "unit_price" in fields:
            fields["unit_price"] = float(fields["unit_price"])
        daftra.update(f"products/{product.daftra_id}.json", {"Product": fields})
    except daftra.DaftraError as error:
        raise ExternalFailure(f"تعذر تعديل المنتج في دفترة، فلم يُحفظ التعديل: {error}")


def delete_in_daftra(product: Product):
    """Deletes the Daftra product it is linked to, before the portal's own goes. Daftra refusing
    (e.g. it has stock movements) raises, so neither is deleted; one already gone there is fine."""
    if product.daftra_id is None:
        return
    try:
        daftra.remove(f"products/{product.daftra_id}.json")
    except daftra.NotFound:
        return
    except daftra.DaftraError as error:
        raise Conflict(f"لم تحذف دفترة المنتج رقم {product.daftra_id}، فلم يُحذف من البوابة أيضًا: {error}. "
                       "يمكنك إيقافه بدلًا من حذفه.")
