"""Loading Daftra's lists before the first user asks for them.

Started in a thread at startup. Not recorded: it runs on every boot and changes nothing.
"""

import logging

from ..core.config import settings
from ..integrations import daftra
from ..modules import clients
from .registry import job

log = logging.getLogger(__name__)


@job("warm_daftra_cache", label="تحميل قوائم دفترة", recorded=False,
     about="Loads Daftra's lists at startup, so the first user does not wait")
def warm_daftra_cache(db, who) -> dict:
    loaded = []
    for load in (daftra.list_staff_members, daftra.list_treasuries, daftra.list_order_sources):
        try:
            load()
            loaded.append(load.__name__)
        except daftra.DaftraError:
            pass
    # The client categories live in our database; they are copied from Daftra only the first time
    if not clients.categories(db):
        try:
            from . import import_client_categories

            import_client_categories.import_client_categories(db, who)
            loaded.append("client_categories")
        except daftra.DaftraError:
            pass
    _ = settings
    return {"loaded": loaded}
