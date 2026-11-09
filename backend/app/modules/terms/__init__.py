"""The terms an invoice prints on its last page (الشروط والأحكام).

A term is a versioned text, never changed once saved. Each package may name one, chosen in the
package's editor. An invoice or estimate prints the term of the first package added to the
request that has one; with none, it prints no terms.
"""

from .models import PackageTerm, Term
from .router import router
from .service import as_html, chosen_for

__all__ = ["PackageTerm", "Term", "as_html", "chosen_for", "router"]
