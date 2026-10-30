"""The Daftra client: the one way the portal talks to our Daftra account.

It knows the account's API and nothing else — not our forms, not our requests, not our tables,
not our wording. Callers ask for a thing by name (`list_treasuries`, `client_category`) and
never write a Daftra path.

What used to live here and does not belong to Daftra has moved out: reading a Daftra address as
our fields and the city table to `modules/clients`, our payment methods as Daftra's keys to
`modules/invoicing`.
"""

from .cache import CACHE_SECONDS, cached, clear, forget
from .client import call, invoice_pdf, upload_file
from .errors import DaftraError, NotFound
from .resources import (
    all_order_sources,
    all_records,
    attach_invoice_document,
    client_category,
    client_invoices,
    create,
    create_order_source,
    get,
    list_client_categories,
    list_clients,
    list_order_sources,
    list_products,
    list_staff,
    list_staff_members,
    list_treasuries,
    post,
    read_v2,
    same_name,
    set_order_source_active,
    update,
    update_unconfirmed,
)

__all__ = [
    "CACHE_SECONDS", "DaftraError", "NotFound", "all_order_sources", "all_records",
    "attach_invoice_document", "cached", "call", "clear", "client_category",
    "client_invoices", "create", "create_order_source", "forget", "get", "invoice_pdf",
    "list_client_categories", "list_clients", "list_order_sources", "list_products", "list_staff",
    "list_staff_members", "list_treasuries", "post", "read_v2", "same_name",
    "set_order_source_active", "update", "update_unconfirmed", "upload_file",
]
