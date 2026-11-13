"""The form engine: what a form is, where the forms put themselves, and what they are built from.

A form lives in `app/forms/<key>/`: a `FormSpec` (`__init__.py`), what it asks (`fields.py`) and,
when approving it creates something in Daftra, what it sends there (`output.py`). The engine never
names a form — a search for a form key outside `app/forms/` finds nothing.

Everything a form's fields.py needs comes from here, which is the only way in (see `final_plan.md`
§4): the switches and the shared sections, the field builders, the choices more than one form
offers, and `FormSpec`/`register`.
"""

from types import SimpleNamespace

from . import sections as _sections
from .fields import INSCRIPTION, OPEN_PRICE_FIELDS, f, files, money, original_refs, yes_no
from .inscriptions import INSCRIPTIONS
from .options import (CASH, CASH_PAYMENT, COLORS, CUSTOMER_TYPE_CODES, CUSTOMER_TYPES,
                      DISCOUNTED, DISCOUNT_AMOUNTS, DISCOUNT_LABELS, EMIRATES, GENDERS, INSTALLATION_WORK, MAX_PACKAGE_QUANTITY, NO_INSCRIPTION,
                      PACKAGE_COLOR_FAMILIES, PACKAGE_INSCRIPTIONS, PAID, PAYMENT_METHODS, PLATE_COLORS, SOURCES,
                      TREASURY_BY_METHOD,
                      YES_NO,
                      installation_work, package_colors, package_quantity)
from .registry import (all_forms, clear, find, form_fields, forms_for, get, keys, known, may,
                       register, visible_forms)
from .spec import ApprovalContext, CheckContext, FormAction, FormSpec
from .switches import HIDE, NEW_CLIENT, REQUIRED, REQUIRED_IF, SHOW, Switch, switched, switched_fields
from .validation import DAFTRA_LIST_TYPES, is_input, sanitize_draft, validate_submission

# The sections many forms share, one switch per field: shared.client(phone=REQUIRED, …). Reached
# by this name, so a form reads `shared.x` for a section it shares and a plain function for its own.
shared = SimpleNamespace(
    request_info=_sections.request_info, client=_sections.client, address=_sections.address,
    amounts=_sections.amounts, payment=_sections.payment, notes=_sections.notes,
)
HAS_REMAINDER = _sections.HAS_REMAINDER

__all__ = [
    # what a form shows and requires: one switch per field
    "HIDE", "SHOW", "REQUIRED", "REQUIRED_IF", "NEW_CLIENT", "Switch", "switched", "switched_fields", "shared",
    "HAS_REMAINDER",
    # what a form is, and how it joins in
    "ApprovalContext", "CheckContext", "FormAction", "FormSpec", "all_forms", "clear", "find", "form_fields",
    "forms_for", "get", "keys", "known", "may", "register", "visible_forms",
    # the building blocks a form's own sections are written with
    "INSCRIPTION", "OPEN_PRICE_FIELDS", "f", "files", "money", "original_refs", "yes_no",
    # the choices more than one form offers
    "INSCRIPTIONS", "CASH", "CASH_PAYMENT", "COLORS", "CUSTOMER_TYPE_CODES", "CUSTOMER_TYPES",
    "DISCOUNTED", "DISCOUNT_AMOUNTS", "DISCOUNT_LABELS", "EMIRATES", "GENDERS", "INSTALLATION_WORK",
    "MAX_PACKAGE_QUANTITY", "NO_INSCRIPTION", "PACKAGE_COLOR_FAMILIES", "PACKAGE_INSCRIPTIONS", "PAID", "PAYMENT_METHODS",
    "PLATE_COLORS", "SOURCES",
    "TREASURY_BY_METHOD", "YES_NO", "installation_work", "package_colors", "package_quantity",
    # validating what comes back
    "DAFTRA_LIST_TYPES", "is_input", "sanitize_draft", "validate_submission",
]
