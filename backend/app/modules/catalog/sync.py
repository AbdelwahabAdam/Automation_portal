"""Refreshing the catalog's linked products from Daftra.

Only the products linked to Daftra (`daftra_id`) are refreshed — their name, price and whether
they are active. Daftra's other products are never added: the catalog is curated, and Daftra's
list is mostly unpriced placeholders and duplicate names. A Daftra product with no price never
clears ours.
"""

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.text import squash
from ...integrations import daftra
from ..audit import log as audit_log
from .models import Product


def _price(raw) -> Decimal | None:
    try:
        price = Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return price if price > 0 else None


def sync_from_daftra(db: Session, who: Actor) -> dict:
    """Refreshes name, price and active of the linked products, in the caller's transaction."""
    remote = {int(product["id"]): product for product in daftra.list_products()}
    linked = list(db.scalars(select(Product).where(Product.daftra_id.is_not(None)).order_by(Product.name)))
    changed, missing, skipped = [], [], []
    unchanged = 0
    for product in linked:
        source = remote.get(product.daftra_id)
        if source is None:
            # Deleted in Daftra, or the link is wrong: reported, left as it is
            missing.append({"id": product.id, "name": product.name, "daftra_id": product.daftra_id})
            continue
        before, after = {}, {}

        name = squash(source.get("name"))
        if name and name != product.name:
            taken = db.scalar(select(Product).where(Product.name == name, Product.id != product.id))
            if taken is not None:
                skipped.append({"id": product.id, "name": product.name,
                                "reason": f"اسمه في دفترة «{name}» مستخدم لمنتج آخر في البوابة"})
            else:
                before["name"], after["name"] = product.name, name
                product.name = name

        price = _price(source.get("unit_price"))
        if price is not None and price != product.unit_price:
            before["unit_price"], after["unit_price"] = float(product.unit_price), float(price)
            product.unit_price = price

        active = str(source.get("deactivate") or "0") != "1"
        if active != product.is_active:
            before["is_active"], after["is_active"] = product.is_active, active
            product.is_active = active

        if not after and not any(item["id"] == product.id for item in skipped):
            unchanged += 1
        if after:
            changed.append({"id": product.id, "name": product.name, "before": before, "after": after})
            audit_log(db, who, "product.daftra_sync", "product", product.id, product.name, before, after)
        # Flushed one by one so the name check above sees the names already changed
        db.flush()
    return {
        "linked": len(linked), "changed": changed, "unchanged": unchanged,
        "missing": missing, "skipped": skipped,
    }


def has_linked_products(db: Session) -> bool:
    return db.scalar(select(Product.id).where(Product.daftra_id.is_not(None)).limit(1)) is not None
