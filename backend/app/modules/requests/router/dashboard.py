"""لوحة المتابعة's one call. Transport only.

One call draws the whole page, so every number on it is of the same moment — and the page says
which moment that was.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.permissions import REVIEW
from ....core.security import require_any_form
from ....core.text import uae_today
from ..service import overview

router = APIRouter(prefix="/api")
# The page is about decisions that are owed, so it takes مراجعة on at least one form. Which forms
# it then counts is decided again in the service, form by form.
manager = require_any_form(REVIEW)


@router.get("/dashboard")
def dashboard(start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
              form_type: str = "", employee: int | None = None, sort: str = "oldest",
              user=Depends(manager), db: Session = Depends(get_db)):
    """The five cards and the waiting list. Without dates, the month so far, in UAE time."""
    first, today = overview.this_month(uae_today())
    return overview.dashboard(db, user, start or first, end or today, form_type, employee, sort)
