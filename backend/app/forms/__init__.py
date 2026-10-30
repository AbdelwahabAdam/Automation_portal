"""Every form the portal knows, one folder each.

Importing a form registers it (`app/forms/<key>/__init__.py`), so the order here is the
order they appear in النماذج. To add a form, make its folder and add it here — nothing else.
"""

from . import (
    new_sale,
    contract_renewal,
    maintenance,
    balance_payment,
    quotation,
    quote_to_invoice,
    order_addition,
    order_modification,
    return_refund,
    tech_cash_collection,
    reinstallation,
    data_entry_error,
    pre_sale_inspection,
    installation_completed,
    contract_service_done,
    open_ticket,
    close_ticket,
    daily_visits,
    tech_extra_works,
)

# The form folders that were loaded, in order. `form_engine.all_forms()` is the list of what
# they registered; this is only the modules themselves.
FORMS = (
    new_sale,
    contract_renewal,
    maintenance,
    balance_payment,
    quotation,
    quote_to_invoice,
    order_addition,
    order_modification,
    return_refund,
    tech_cash_collection,
    reinstallation,
    data_entry_error,
    pre_sale_inspection,
    installation_completed,
    contract_service_done,
    open_ticket,
    close_ticket,
    daily_visits,
    tech_extra_works,
)

__all__ = ["FORMS"]
