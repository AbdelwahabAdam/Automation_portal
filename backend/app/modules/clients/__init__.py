"""The portal's customers — "the client for the portal", as against the Daftra client.

Daftra stays the source of truth; the portal keeps a copy so a form can find a client by phone
or code at once. This module owns `clients`, `addresses` and `client_categories`, and holds
everything the portal knows about a customer: finding one by phone or code, whether a request's
client is new, their addresses here and in Daftra, the categories with the place each stands for,
a client's open invoices, creating the client in Daftra when an approved request needs one, and
reading a Google Maps link.
"""

from .in_daftra import (CATEGORY_LOCATIONS, CITY_LOCATIONS, address_change, address_fields,
                        address_from_daftra, categories_with_location, city_location, client_id,
                        create_client, custom_fields, existing_client_id, held_custom_fields,
                        invoice_label, known_client, open_invoices, save_address, update_client,
                        usable_link)
from .models import Address, Client, ClientCategory
from .router import router
from .service import address_out, categories, client_match, details_from_daftra, lookup
from .sync import client_rows, resend_held_addresses, sync_from_daftra

__all__ = [
    "Address", "CATEGORY_LOCATIONS", "CITY_LOCATIONS", "Client", "ClientCategory", "address_change",
    "address_fields", "address_from_daftra", "address_out", "categories", "categories_with_location",
    "city_location", "client_id", "client_match", "create_client", "custom_fields", "details_from_daftra",
    "client_rows", "existing_client_id", "held_custom_fields", "invoice_label", "known_client", "lookup",
    "open_invoices", "resend_held_addresses", "router", "save_address", "sync_from_daftra",
    "update_client", "usable_link",
]
