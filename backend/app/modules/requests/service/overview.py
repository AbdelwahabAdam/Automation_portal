"""لوحة المتابعة: the five numbers at the top of it, and the work still waiting on someone.

Every number here is about the forms the manager may *review*. Holding عرض on a form shows its
requests in المراجعة but puts nothing on this page: the page is about decisions that are owed.

The period is read in UAE time, because that is the day the office works to. Both chosen days
are inside it. Two of the five cards ignore the period on purpose — a backlog is what is waiting
now, whenever it was sent.
"""

from datetime import date, datetime, time, timedelta, timezone
from statistics import median

from sqlalchemy.orm import Session

from ....core.errors import Invalid
from ....core.permissions import REVIEW
from ....core.text import UAE
from ... import form_engine
from .. import repo
from . import access
from .review import form_label

#: At most this many waiting requests are listed; the count above the list is the true total
ATTENTION_LIMIT = 200
#: A period longer than this is not drawn day by day: the line would be unreadable and the answer huge
TREND_LIMIT_DAYS = 400
#: How «محتاج متابعة منك» may be ordered. The work to do first, or what has just come in.
SORTS = ("oldest", "newest")


def this_month(today: date) -> tuple[date, date]:
    """The period the page opens on: the first of this month until today."""
    return today.replace(day=1), today


def uae_range(start: date, end: date) -> tuple[datetime, datetime]:
    """The two days as the moment the first begins and the moment after the last ends.

    Both days are inside the period, so a request made at 11pm on the last day counts. UAE time
    throughout: a request sent at 1am in Dubai belongs to that day, not to the day before in UTC.
    """
    if start > end:
        raise Invalid("تاريخ البداية بعد تاريخ النهاية")
    return datetime.combine(start, time.min, UAE), datetime.combine(end + timedelta(days=1), time.min, UAE)


def reviewable(user) -> list[str]:
    """The forms this page is about: the ones the user may decide on."""
    return [spec.key for spec in form_engine.forms_for(user, REVIEW)]


def scope(user, form_type: str) -> list[str]:
    """Those forms, narrowed to the one picked in نوع النموذج."""
    mine = reviewable(user)
    if not form_type:
        return mine
    if form_type not in mine:
        raise Invalid("هذا النموذج غير متاح لك")
    return [form_type]


def hours(waits: list[float]) -> float | None:
    """The middle wait, to one decimal. None when nothing was decided: «لا توجد بيانات», not zero."""
    return round(median(waits), 1) if waits else None


def days_of(start: date, end: date) -> list[date]:
    """Every day of the period, so a day nothing happened on is a zero rather than a gap."""
    return [start + timedelta(days=step) for step in range((end - start).days + 1)]


def trend(db: Session, forms: list[str], employee_id: int | None, start: date, end: date) -> list[dict]:
    """The period day by day: how many were sent, and how many were approved.

    A very long period is left undrawn rather than answered with hundreds of points: the cards
    above still count it, and the line would say nothing a reader could use.
    """
    days = days_of(start, end)
    if len(days) > TREND_LIMIT_DAYS:
        return []
    begins, ends = uae_range(start, end)
    sent = repo.submitted_by_day(db, forms, employee_id, begins, ends)
    approved = repo.approved_by_day(db, forms, employee_id, begins, ends)
    return [{"day": day.isoformat(), "submitted": sent.get(day.isoformat(), 0),
             "approved": approved.get(day.isoformat(), 0)} for day in days]


def by_form(db: Session, forms: list[str], employee_id: int | None, start: date, end: date) -> list[dict]:
    """The same period split by نوع النموذج, the busiest form first.

    Only the forms that had something: a list of every form with zeros tells the reader nothing.
    """
    begins, ends = uae_range(start, end)
    sent = repo.submitted_by_form(db, forms, employee_id, begins, ends)
    approved = repo.approved_by_form(db, forms, employee_id, begins, ends)
    rows = [{"key": key, "label": form_label(key), "submitted": sent.get(key, 0),
             "approved": approved.get(key, 0)}
            for key in {**sent, **approved}]
    return sorted(rows, key=lambda row: (-row["submitted"], -row["approved"], row["label"]))


def before(start: date, end: date) -> tuple[date, date]:
    """The period of the same length immediately before this one, to compare against."""
    length = (end - start).days + 1
    last = start - timedelta(days=1)
    return last - timedelta(days=length - 1), last


def totals(db: Session, forms: list[str], employee_id: int | None, start: date, end: date) -> dict:
    """The three numbers a period is compared by."""
    begins, ends = uae_range(start, end)
    waits = [waited for _, waited in repo.review_waits(db, forms, employee_id, begins, ends)]
    return {"submitted": repo.submitted_in(db, forms, employee_id, begins, ends),
            "approved": repo.approved_in(db, forms, employee_id, begins, ends),
            "review_hours": hours(waits), "review_count": len(waits)}


def attention_row(request, user) -> dict:
    """One line of «محتاج متابعة منك»."""
    return {
        "id": request.id, "form_type": request.form_type, "form_label": form_label(request.form_type),
        "customer_name": (request.data or {}).get("customer_name") or "",
        "owner_id": request.created_by_id, "owner_name": request.created_by_name,
        "status": request.status,
        # Awaiting review: since it was last sent. Awaiting the employee: since it was returned.
        "waiting_since": request.submitted_at if request.status == "submitted" else request.reviewed_at,
        "returned_reason": request.returned_reason or "",
        # A manager does not decide on a request they wrote themselves, so they are offered عرض
        "can_review": access.can_review(request, user) and (user.is_admin or request.created_by_id != user.id),
    }


def dashboard(db: Session, user, start: date, end: date, form_type: str = "",
              employee_id: int | None = None, sort: str = "oldest") -> dict:
    """Everything the page draws, read in one go so every number is of the same moment."""
    forms = scope(user, form_type)
    if sort not in SORTS:
        raise Invalid("ترتيب غير معروف")
    pending = repo.pending_requests(db, forms, employee_id, ATTENTION_LIMIT, newest_first=sort == "newest")
    period = totals(db, forms, employee_id, start, end)
    earlier_start, earlier_end = before(start, end)
    return {
        "from": start.isoformat(), "to": end.isoformat(),
        "refreshed_at": datetime.now(timezone.utc),
        # The filters' own choices, always the whole scope: picking a form must not empty الموظف
        "forms": [{"key": spec.key, "label": spec.label} for spec in form_engine.forms_for(user, REVIEW)],
        "employees": [{"id": request.created_by_id, "name": request.created_by_name}
                      for request in repo.owners(db, reviewable(user))],
        "cards": {
            **period,
            "awaiting_review": repo.waiting_now(db, forms, employee_id, "submitted"),
            "awaiting_updates": repo.waiting_now(db, forms, employee_id, "returned"),
        },
        # The same length of time immediately before, so each card can say which way it is going
        "before": {"from": earlier_start.isoformat(), "to": earlier_end.isoformat(),
                   **totals(db, forms, employee_id, earlier_start, earlier_end)},
        "sort": sort,
        "trend": trend(db, forms, employee_id, start, end),
        "by_form": by_form(db, forms, employee_id, start, end),
        "attention": [attention_row(request, user) for request in pending],
    }
