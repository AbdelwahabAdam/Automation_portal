"""Every table the portal has, in one import.

A module owns its own tables (`modules/<module>/models.py`); this is the one place that
names them all, so SQLAlchemy has every mapper before the first query and Alembic sees
every table. Nothing but an entry point and Alembic imports this.

`jobs/models.py` is not here: jobs sit above the modules, so an entry point imports that one
itself (see `main.py` and `alembic/env.py`).
"""

from .audit.models import AuditLog
from .catalog.models import Package, PackageItem, Product
from .clients.models import Address, Client, ClientCategory
from .identity.models import Role, User, user_roles
from .requests.models import Attachment, Request, RequestDocument, RequestEvent

__all__ = ["Address", "Attachment", "AuditLog", "Client", "ClientCategory", "Package", "PackageItem",
           "Product", "Request", "RequestDocument", "RequestEvent", "Role", "User", "user_roles"]
