"""The portal's customers — "the client for the portal", as against the Daftra client.

Daftra stays the source of truth; the portal keeps a copy so a form can find a client by phone
or code at once. The rest of this module arrives in phase 4; what is here now is the knowledge
that left the Daftra client.
"""

from .in_daftra import (
    CATEGORY_LOCATIONS,
    CITY_LOCATIONS,
    address_from_daftra,
    categories_with_location,
    city_location,
    invoice_label,
    open_invoices,
)

__all__ = ["CATEGORY_LOCATIONS", "CITY_LOCATIONS", "address_from_daftra", "categories_with_location",
           "city_location", "invoice_label", "open_invoices"]
