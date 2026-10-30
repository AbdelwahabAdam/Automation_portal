"""Manager review of submitted requests: approve, or return to the salesperson with a reason.

A request goes draft -> submitted -> returned or approved. A returned request can be corrected
and submitted again by its owner, which starts a new revision. Every step is kept in its history.

This never names a form. What approving one creates in Daftra is the form's own
(`app/forms/<key>/hooks.py`), and it is asked for it through the registry — which is why this
module does not import `invoicing` at all.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ....core.config import settings
from ....core.context import Actor
from ....core.errors import DomainError, Invalid, SyncError
from ....core.text import display_name
from ... import form_engine, notifications
from ...audit import log as audit_log
from .. import repo
from ..labels import request_label
from ..models import Request, RequestEvent
from . import access

log = logging.getLogger(__name__)

EVENT_LABELS = {
    "created": "إنشاء المسودة",
    "submitted": "إرسال للمراجعة",
    "resubmitted": "إعادة الإرسال بعد التعديل",
    "returned": "إعادة للتعديل",
    "approved": "اعتماد الطلب",
}
# Shorter than this is not a reason the employee can act on
MIN_REASON = 5


def form_label(form_type: str) -> str:
    """The form's name as the review screens show it; its key if it is no longer registered."""
    spec = form_engine.find(form_type)
    return spec.label if spec else form_type


def add_event(db: Session, request: Request, user, kind: str, note: str | None = None):
    db.add(RequestEvent(request=request, user_id=user.id, username=display_name(user), kind=kind,
                        revision=request.revision, note=note))


def review_out(request: Request) -> dict:
    return {
        "id": request.id, "form_type": request.form_type, "data": request.data, "status": request.status,
        "revision": request.revision, "returned_reason": request.returned_reason,
        "created_at": request.created_at, "updated_at": request.updated_at,
        "submitted_at": request.submitted_at, "reviewed_at": request.reviewed_at,
        "reviewed_by_name": display_name(request.reviewed_by) if request.reviewed_by else None,
        "created_by_id": request.created_by_id, "created_by_name": display_name(request.created_by),
        "daftra_invoice_no": request.daftra_invoice_no, "daftra_receipt_no": request.daftra_receipt_no,
        "daftra_work_order_no": request.daftra_work_order_no, "daftra_estimate_no": request.daftra_estimate_no,
        "daftra_error": request.daftra_error,
    }


def queue(db: Session, user) -> list[dict]:
    """Only the requests of the forms this user may view or review, each saying whether they may
    decide on it — a reviewer of one form does not see another's requests at all."""
    wanted = access.reviewable_form_keys(user)
    return [{**review_out(request), "can_review": access.can_review(request, user)}
            for request in repo.queue(db, wanted)]


def history(request: Request) -> list[dict]:
    return [
        {"at": event.at, "kind": event.kind, "label": EVENT_LABELS.get(event.kind, event.kind),
         "username": event.username, "revision": event.revision, "note": event.note}
        for event in request.events
    ]


def notify_owner(request: Request, reviewer, approved: bool) -> bool:
    """Tells the salesperson by email. Never blocks the decision: a failed email is only recorded."""
    owner = request.created_by
    if not owner.email or not owner.is_active:
        return False
    values = {
        "full_name": display_name(owner), "request_id": request.id,
        "form_label": form_label(request.form_type),
        "customer_name": request.data.get("customer_name") or "—", "reviewer": display_name(reviewer),
        # Straight to the request itself, which opens from a fresh tab
        "link": f"{settings.public_url.rstrip('/')}/requests/{request.id}",
    }
    try:
        if approved:
            notifications.send(owner.email, *notifications.compose("request_approved", **values))
        else:
            notifications.send(owner.email, *notifications.compose(
                "request_returned", reason=request.returned_reason, **values))
        return True
    except notifications.MailError:
        return False


def record_failure(db: Session, who: Actor, request: Request, message: str):
    """Saves why the Daftra documents could not all be created, with the ids of those that were."""
    request.daftra_error = message
    audit_log(db, who, "request.daftra_failed", "request", request.id, request_label(request),
              after={"error": message})
    try:
        db.commit()
    except Exception:
        # The fault left the session unusable (a database error); nothing more can be saved now
        log.exception("Could not save the Daftra failure of request %s", request.id)
        db.rollback()


def approve(db: Session, who: Actor, request_id: int, revision: int) -> dict:
    user = who.user
    request = repo.lock(db, request_id)
    access.check_can_decide(request, user, revision)
    summary = {}
    spec = form_engine.find(request.form_type)
    if spec is not None and spec.on_approve:
        try:
            summary = spec.on_approve(
                form_engine.ApprovalContext(request=request, db=db, reviewer=user))
            request.daftra_error = None
            request.daftra_synced_at = datetime.now(timezone.utc)
        except SyncError as error:
            # The request stays submitted; what was created so far is kept, so approving again carries on
            record_failure(db, who, request, str(error))
            raise
        except Exception as error:
            # A fault of ours midway: still keep the ids of what Daftra already created
            log.exception("Creating the Daftra documents of request %s failed", request.id)
            message = f"خطأ غير متوقع أثناء الإنشاء في دفترة: {error}"
            record_failure(db, who, request, message)
            raise Unexpected(message) from error
    request.status = "approved"
    request.returned_reason = None
    request.reviewed_by = user
    request.reviewed_at = datetime.now(timezone.utc)
    add_event(db, request, user, "approved")
    db.flush()
    emailed = notify_owner(request, user, approved=True)
    audit_log(db, who, "request.approve", "request", request.id, request_label(request),
              after={"status": "approved", "email_sent": emailed, **summary})
    db.commit()
    return review_out(request)


def return_to_owner(db: Session, who: Actor, request_id: int, revision: int, raw_reason: str) -> dict:
    user = who.user
    reason = raw_reason.strip()
    if len(reason) < MIN_REASON:
        raise Invalid("اكتب سبب الإعادة بوضوح ليعرف الموظف ما المطلوب تعديله")
    request = db.get(Request, request_id)
    access.check_can_decide(request, user, revision)
    request.status = "returned"
    request.returned_reason = reason
    request.reviewed_by = user
    request.reviewed_at = datetime.now(timezone.utc)
    add_event(db, request, user, "returned", reason)
    db.flush()
    emailed = notify_owner(request, user, approved=False)
    audit_log(db, who, "request.return", "request", request.id, request_label(request),
              after={"status": "returned", "reason": reason, "email_sent": emailed})
    db.commit()
    return review_out(request)


class Unexpected(DomainError):
    """A fault of ours while creating the Daftra documents: answered 500, as before."""

    status_code = 500
