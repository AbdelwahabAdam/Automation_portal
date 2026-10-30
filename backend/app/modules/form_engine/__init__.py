"""Form definitions and their validation.

The frontend renders forms from these definitions and the backend validates
submissions against the same definitions, so a form is described in one place.
The forms follow the sales templates in forms.md.
"""

from .definitions import FORM_TYPES, VISIBLE_FORM_TYPES, form_fields, list_form_types
from .options import EMIRATES, NO_INSCRIPTION, PAYMENT_METHODS, package_colors, package_quantity
from .validation import DAFTRA_LIST_TYPES, is_input, sanitize_draft, validate_submission

__all__ = ["DAFTRA_LIST_TYPES", "EMIRATES", "FORM_TYPES", "NO_INSCRIPTION", "PAYMENT_METHODS", "VISIBLE_FORM_TYPES",
           "form_fields", "is_input", "list_form_types", "package_colors", "package_quantity", "sanitize_draft",
           "validate_submission"]
