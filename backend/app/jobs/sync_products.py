"""Refreshing the catalog's products linked to Daftra, from the «المزامنة مع دفترة» page.

The rules live in `modules/catalog`; this only runs them.
"""

from ..modules import catalog
from .registry import job


@job("sync_products", label="المنتجات", on_admin_page=True,
     about="Refreshes the linked products' name, price and active from Daftra")
def sync_products(db, who) -> dict:
    return catalog.sync_from_daftra(db, who)
