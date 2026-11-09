"""The queries on requests' own tables. No commits, no decisions."""

import shutil
import uuid
from pathlib import Path

from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, selectinload

from ...core.config import UPLOAD_DIR
from .models import Attachment, Request, RequestDocument, RequestEvent


def count_by_owner(db: Session, user_id: int) -> int:
    """How many requests this user has made. A user with any is stopped, not deleted."""
    return db.scalar(select(func.count()).select_from(Request).where(Request.created_by_id == user_id))


def by_owner(db: Session, user_id: int, limit: int = 200) -> list[Request]:
    return list(db.scalars(
        select(Request).where(Request.created_by_id == user_id)
        .options(selectinload(Request.attachments), selectinload(Request.documents))
        .order_by(Request.updated_at.desc()).limit(limit)
    ))


def counts_by_status(db: Session, user_id: int) -> dict:
    rows = db.execute(
        select(Request.status, func.count()).where(Request.created_by_id == user_id).group_by(Request.status)
    )
    return dict(rows.all())


def queue(db: Session, form_types: list[str], limit: int = 1000) -> list[Request]:
    """The requests of these forms, newest first: those sent, and the employees' drafts, a draft
    by when it was last saved. Only the forms the reviewer may see are asked for."""
    if not form_types:
        return []
    return list(db.scalars(
        select(Request).where(Request.form_type.in_(form_types))
        .options(selectinload(Request.created_by), selectinload(Request.reviewed_by),
                 selectinload(Request.documents))
        .order_by(func.coalesce(Request.submitted_at, Request.updated_at).desc()).limit(limit)
    ))


def document_holder(db: Session, kind: str, external_id: int) -> int | None:
    """Which request a document Daftra made belongs to, if any of them holds it."""
    return db.scalar(select(RequestDocument.request_id)
                     .where(RequestDocument.kind == kind, RequestDocument.external_id == external_id).limit(1))


def lock(db: Session, request_id: int):
    """Held until the commit, so two managers approving at once cannot both create the documents."""
    db.execute(select(Request.id).where(Request.id == request_id).with_for_update())
    return db.get(Request, request_id)


def remove_folder(request_id: int):
    shutil.rmtree(UPLOAD_DIR / str(request_id), ignore_errors=True)


def save_file(db: Session, request, field: str, filename: str, content: bytes,
              content_type: str = "application/pdf") -> Attachment:
    """Puts a file in the request's folder and records it as one of its attachments.

    `invoicing` draws the invoice, receipt and work-order PDFs and names them; the attachments
    table is this module's, so the saving happens here.
    """
    folder = UPLOAD_DIR / str(request.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex + Path(filename).suffix.lower()
    (folder / stored_name).write_bytes(content)
    attachment = Attachment(request=request, field=field, filename=filename[:255],
                            stored_name=stored_name, content_type=content_type, size=len(content))
    db.add(attachment)
    return attachment


# ---------- What لوحة المتابعة counts (service/overview) ----------

#: A request still waiting on someone: on a reviewer's decision, or on its own employee
PENDING = ("submitted", "returned")
#: The two ways a review ends, either of which is the decision an employee waited for
DECISIONS = ("approved", "returned")


def _scoped(stmt, form_types: list[str], employee_id: int | None):
    """Narrows a query to the forms the manager may review and, if one is picked, to one employee.

    The employee is the request's own — who wrote it — never whoever reviewed it.
    """
    stmt = stmt.where(Request.form_type.in_(form_types))
    return stmt if employee_id is None else stmt.where(Request.created_by_id == employee_id)


def _first_submitted():
    """When each request was first sent. There is one `submitted` event per request: sending a
    returned one again writes `resubmitted`, and saving a draft writes nothing at all."""
    return (select(RequestEvent.request_id, func.min(RequestEvent.at).label("at"))
            .where(RequestEvent.kind == "submitted").group_by(RequestEvent.request_id).subquery())


def _first_decision():
    """The first decision taken on each request — approved or returned — and who took it."""
    return (select(RequestEvent.request_id, RequestEvent.at, RequestEvent.user_id)
            .where(RequestEvent.kind.in_(DECISIONS))
            .ext(distinct_on(RequestEvent.request_id))
            .order_by(RequestEvent.request_id, RequestEvent.at, RequestEvent.id).subquery())


def submitted_in(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> int:
    """Requests first sent inside the period. One request counts once, however often it came back."""
    sent = _first_submitted()
    stmt = (select(func.count()).select_from(Request).join(sent, sent.c.request_id == Request.id)
            .where(sent.c.at >= begins, sent.c.at < ends))
    return db.scalar(_scoped(stmt, form_types, employee_id))


def approved_in(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> int:
    """Requests approved inside the period, whenever they were sent. Approval is the end of a
    request's life, so `reviewed_at` is the moment it was approved."""
    stmt = (select(func.count()).select_from(Request)
            .where(Request.status == "approved", Request.reviewed_at >= begins, Request.reviewed_at < ends))
    return db.scalar(_scoped(stmt, form_types, employee_id))


def waiting_now(db: Session, form_types: list[str], employee_id: int | None, status: str) -> int:
    """How many are in that state right now — the backlog, whenever it was sent."""
    stmt = select(func.count()).select_from(Request).where(Request.status == status)
    return db.scalar(_scoped(stmt, form_types, employee_id))


def review_waits(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> list[tuple[int, float]]:
    """(request id, hours waited) for each request whose first decision fell inside the period.

    A request decided by its own author is left out: nobody waited on another person for it.
    """
    sent, decided = _first_submitted(), _first_decision()
    stmt = (select(Request.id, decided.c.at, sent.c.at)
            .join(sent, sent.c.request_id == Request.id)
            .join(decided, decided.c.request_id == Request.id)
            .where(decided.c.at >= begins, decided.c.at < ends,
                   or_(decided.c.user_id.is_(None), decided.c.user_id != Request.created_by_id)))
    return [(request_id, (at - sent_at).total_seconds() / 3600)
            for request_id, at, sent_at in db.execute(_scoped(stmt, form_types, employee_id)).all()]


def waiting_since():
    """When the current wait began: the last time it was sent, or the time it was returned."""
    return case((Request.status == "submitted", Request.submitted_at), else_=Request.reviewed_at)


def pending_requests(db: Session, form_types: list[str], employee_id: int | None, limit: int = 200,
                     newest_first: bool = False) -> list[Request]:
    """Everything still waiting. No period: old work stays in sight.

    The longest wait first, which is the order the work should be done in — or the other way
    round, for a manager looking at what has just come in. The order is chosen here and not in
    the browser because only the first `limit` of them are sent: sorting the page that arrived
    would answer «الأحدث» with the newest of the oldest.
    """
    column = waiting_since()
    order = column.desc().nulls_last() if newest_first else column.asc().nulls_last()
    stmt = (select(Request).options(selectinload(Request.created_by))
            .where(Request.status.in_(PENDING)).order_by(order).limit(limit))
    return list(db.scalars(_scoped(stmt, form_types, employee_id)))


def owners(db: Session, form_types: list[str]) -> list[Request]:
    """One request per employee who has sent one, to name the الموظف filter's choices."""
    if not form_types:
        return []
    return list(db.scalars(
        select(Request).options(selectinload(Request.created_by))
        .where(Request.form_type.in_(form_types), Request.status != "draft")
        .ext(distinct_on(Request.created_by_id)).order_by(Request.created_by_id, Request.id)))


def review_milestones(db: Session, request_ids: list[int]) -> dict[int, dict]:
    """For each of those requests: when it was first sent, when it was first decided on, and how
    long that took — what المراجعة needs to show the same requests لوحة المتابعة counted.

    `review_hours` is empty for a request nobody has decided on yet, and for one decided by its
    own author, which is the wait لوحة المتابعة leaves out of زمن المراجعة.
    """
    if not request_ids:
        return {}
    sent, decided = _first_submitted(), _first_decision()
    stmt = (select(Request.id, sent.c.at, decided.c.at, decided.c.user_id, Request.created_by_id)
            .outerjoin(sent, sent.c.request_id == Request.id)
            .outerjoin(decided, decided.c.request_id == Request.id)
            .where(Request.id.in_(request_ids)))
    found = {}
    for request_id, sent_at, decided_at, decided_by, owner_id in db.execute(stmt).all():
        waited = None
        if sent_at is not None and decided_at is not None and decided_by != owner_id:
            waited = round((decided_at - sent_at).total_seconds() / 3600, 1)
        found[request_id] = {"first_submitted_at": sent_at, "first_decision_at": decided_at,
                             "review_hours": waited}
    return found


# ---------- The shape of the period (service/overview's charts) ----------

#: The office's own day, which is what every date on the page is counted in
UAE_ZONE = "Asia/Dubai"


def _uae_day(column):
    """The UAE day a moment falls on. Counted in the database so a day is grouped once.

    The same expression object goes in the SELECT and the GROUP BY: built twice it carries two
    different bind parameters for the zone, and Postgres then refuses to see them as one column.
    """
    return cast(func.timezone(UAE_ZONE, column), Date)


def submitted_by_day(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> dict:
    """{day: how many were first sent that day}. Days with none are simply absent."""
    sent = _first_submitted()
    day = _uae_day(sent.c.at)
    stmt = (select(day, func.count()).select_from(Request)
            .join(sent, sent.c.request_id == Request.id)
            .where(sent.c.at >= begins, sent.c.at < ends).group_by(day))
    return {day.isoformat(): count for day, count in db.execute(_scoped(stmt, form_types, employee_id)).all()}


def approved_by_day(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> dict:
    """{day: how many were approved that day}."""
    day = _uae_day(Request.reviewed_at)
    stmt = (select(day, func.count()).select_from(Request)
            .where(Request.status == "approved", Request.reviewed_at >= begins, Request.reviewed_at < ends)
            .group_by(day))
    return {day.isoformat(): count for day, count in db.execute(_scoped(stmt, form_types, employee_id)).all()}


def submitted_by_form(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> dict:
    """{form key: how many of it were first sent in the period}."""
    sent = _first_submitted()
    stmt = (select(Request.form_type, func.count()).select_from(Request)
            .join(sent, sent.c.request_id == Request.id)
            .where(sent.c.at >= begins, sent.c.at < ends).group_by(Request.form_type))
    return dict(db.execute(_scoped(stmt, form_types, employee_id)).all())


def approved_by_form(db: Session, form_types: list[str], employee_id: int | None, begins, ends) -> dict:
    """{form key: how many of it were approved in the period}."""
    stmt = (select(Request.form_type, func.count()).select_from(Request)
            .where(Request.status == "approved", Request.reviewed_at >= begins, Request.reviewed_at < ends)
            .group_by(Request.form_type))
    return dict(db.execute(_scoped(stmt, form_types, employee_id)).all())
