"""The form engine: what a form is, where the forms put themselves, and what they are built from.

A form lives in `app/forms/<key>/`: a `FormSpec` and its fields, plus hooks only where it differs.
The engine never names a form — a search for a form key outside `app/forms/` finds nothing.

Everything a form folder needs comes from here, which is the only way in (see `final_plan.md` §4):
the field builders, the choices more than one form offers, and `FormSpec`/`register`.
"""

from .fields import (INSCRIPTION, NOTES, address, amounts, attachments, client, client_kind, discount_fields, f, files,
                     money, need, original_refs, payment, request_info, section, yes_no)
from .inscriptions import INSCRIPTIONS
from .options import (AREAS, AREAS_BY_EMIRATE, CASH, CASH_PAYMENT, COLORS, CUSTOMER_TYPE_CODES, CUSTOMER_TYPES,
                      DISCOUNTED, DISCOUNT_AMOUNTS, DISCOUNT_LABELS, EMIRATES, GENDERS, INSTALLATION_WORK, MAX_PACKAGE_QUANTITY, NO_INSCRIPTION,
                      PACKAGE_COLOR_FAMILIES, PAID, PAYMENT_METHODS, SOURCES, TREASURY_BY_METHOD, YES_NO,
                      installation_work, package_colors, package_quantity)
from .registry import (all_forms, clear, find, form_fields, forms_for, get, keys, known, may,
                       register, visible_forms)
from .spec import ApprovalContext, CheckContext, FormSpec
from .validation import DAFTRA_LIST_TYPES, is_input, sanitize_draft, validate_submission

__all__ = [
    # what a form is, and how it joins in
    "ApprovalContext", "CheckContext", "FormSpec", "all_forms", "clear", "find", "form_fields",
    "forms_for", "get", "keys", "known", "may", "register", "visible_forms",
    # the building blocks a form's fields are written with
    "INSCRIPTION", "NOTES", "address", "amounts", "attachments", "client", "client_kind", "discount_fields", "f", "files",
    "money", "need", "original_refs", "payment", "request_info", "section", "yes_no",
    # the choices more than one form offers
    "INSCRIPTIONS", "AREAS", "AREAS_BY_EMIRATE", "CASH", "CASH_PAYMENT", "COLORS", "CUSTOMER_TYPE_CODES", "CUSTOMER_TYPES",
    "DISCOUNTED", "DISCOUNT_AMOUNTS", "DISCOUNT_LABELS", "EMIRATES", "GENDERS", "INSTALLATION_WORK",
    "MAX_PACKAGE_QUANTITY", "NO_INSCRIPTION", "PACKAGE_COLOR_FAMILIES", "PAID", "PAYMENT_METHODS", "SOURCES",
    "TREASURY_BY_METHOD", "YES_NO", "installation_work", "package_colors", "package_quantity",
    # validating what comes back
    "DAFTRA_LIST_TYPES", "is_input", "sanitize_draft", "validate_submission",
]
