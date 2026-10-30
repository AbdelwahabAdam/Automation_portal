"""A request: its draft, its files, its history, its review, and what approving it created.

All forms share one table, one lifecycle, one validator and one review queue; what differs
between forms lives in `app/forms/<key>/`, and approving asks the form through the registry —
which is why this module does not import `invoicing` at all.

This module owns `requests`, `attachments` and `request_events`. `invoicing` saves the PDFs it
draws through `save_file`, because the attachments table is this module's.
"""

from .labels import request_label
from .models import Attachment, Request, RequestEvent
from .repo import count_by_owner, save_file
from .router import router
from .service.access import can_view
from .service.review import form_label

__all__ = ["Attachment", "Request", "RequestEvent", "can_view", "count_by_owner", "form_label",
           "request_label", "router", "save_file"]
