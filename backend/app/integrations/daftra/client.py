"""The one switch: every call that would reach Daftra's network goes to the live account or to
the stand-in, and nothing above here knows which it got.

`DAFTRA_FAKE=true` picks the fake (see the README's "Run"). It is on by default on a local
machine, so a portal on someone's laptop cannot write to the live account by accident, and it
cannot be on on the server: the production compose file hard-codes it off, and the portal
refuses to start with it on and a real version.
"""

from ...core.config import settings


def _backend():
    from . import fake, live

    return fake if settings.daftra_fake else live


def call(method: str, path: str, params: dict | None = None, body: dict | list | None = None) -> dict:
    """path starts at the account's address, e.g. "/api2/invoices.json"."""
    return _backend().call(method, path, params, body)


def upload_file(content: bytes, filename: str, content_type: str,
                entity: str = "invoice", field: str = "invoices.documents") -> int:
    """Puts a file in the account's file store and returns its id."""
    return _backend().upload_file(content, filename, content_type, entity, field)


def invoice_pdf(invoice_id: int, pdf_url: str) -> bytes:
    """The invoice's PDF, as the account prints it."""
    return _backend().invoice_pdf(invoice_id, pdf_url)
