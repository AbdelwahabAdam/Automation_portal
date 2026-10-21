"""Manager review of submitted requests: approve, or return to the salesperson with a reason.

A request goes draft -> submitted -> returned or approved. A returned request can be corrected
and submitted again by its owner, which starts a new revision. Every step is kept in its history.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import daftra_sync, mail
from .audit import Audit, request_label
from .config import settings
from .database import get_db
from .forms import FORM_TYPES
from .models import Request, RequestEvent, User
from .security import get_current_user, require_page
from .text import display_name

log = logging.getLogger(__name__)

REVIEW_PAGE = "sales.review"
router = APIRouter(prefix="/api")
reviewer = require_page(REVIEW_PAGE)

EVENT_LABELS = {
    "created": "إنشاء المسودة",
    "submitted": "إرسال للمراجعة",
    "resubmitted": "إعادة الإرسال بعد التعديل",
    "returned": "إعادة للتعديل",
    "approved": "اعتماد الطلب",
}


def add_event(db: Session, request: Request, user: User, kind: str, note: str | None = None):
    db.add(RequestEvent(request=request, user_id=user.id, username=display_name(user), kind=kind,
                        revision=request.revision, note=note))


def can_view(request: Request, user: User) -> bool:
    """The owner sees their own request; a reviewer sees every request that has been sent."""
    pages = set(user.pages)
    if request.created_by_id == user.id and pages & {"sales.new_request", "sales.my_requests"}:
        return True
    return request.status != "draft" and REVIEW_PAGE in pages


def viewable_request(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Request:
    request = db.get(Request, request_id)
    if request is None or not can_view(request, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الطلب غير موجود")
    return request


def review_out(request: Request) -> dict:
    return {
        "id": request.id, "form_type": request.form_type, "data": request.data, "status": request.status,
        "revision": request.revision, "returned_reason": request.returned_reason,
        "created_at": request.created_at, "updated_at": request.updated_at, "submitted_at": request.submitted_at,
        "reviewed_at": request.reviewed_at,
        "reviewed_by_name": display_name(request.reviewed_by) if request.reviewed_by else None,
        "created_by_id": request.created_by_id, "created_by_name": display_name(request.created_by),
        "daftra_invoice_no": request.daftra_invoice_no, "daftra_receipt_no": request.daftra_receipt_no,
        "daftra_work_order_no": request.daftra_work_order_no, "daftra_error": request.daftra_error,
    }


@router.get("/review/requests")
def review_queue(user: User = Depends(reviewer), db: Session = Depends(get_db)):
    """Every request that has been sent, newest first. Drafts stay private to their owner."""
    requests = db.scalars(
        select(Request).where(Request.status != "draft")
        .options(selectinload(Request.created_by), selectinload(Request.reviewed_by))
        .order_by(Request.submitted_at.desc()).limit(1000)
    ).all()
    return [review_out(request) for request in requests]


@router.get("/requests/{request_id}/history")
def request_history(request: Request = Depends(viewable_request)):
    return [
        {"at": event.at, "kind": event.kind, "label": EVENT_LABELS.get(event.kind, event.kind),
         "username": event.username, "revision": event.revision, "note": event.note}
        for event in request.events
    ]


class DecisionIn(BaseModel):
    # The revision the reviewer looked at; a request changed since then is refused
    revision: int


class ReturnIn(DecisionIn):
    reason: str = Field(min_length=1, max_length=2000)


def reviewable(request_id: int, body: DecisionIn, user: User, db: Session) -> Request:
    request = db.get(Request, request_id)
    if request is None or request.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الطلب غير موجود")
    if request.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "تمت مراجعة هذا الطلب بالفعل. حدّث الصفحة لرؤية حالته الحالية.")
    if request.revision != body.revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "تغيّر الطلب منذ فتحته. حدّث الصفحة وراجع النسخة الحالية.")
    # A manager does not decide on their own request; the system admin can
    if request.created_by_id == user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "لا يمكنك مراجعة طلب أرسلته بنفسك. يراجعه مدير آخر.")
    return request


def notify_owner(request: Request, reviewer_user: User, approved: bool) -> bool:
    """Tells the salesperson by email. Never blocks the decision: a failed email is only recorded."""
    owner = request.created_by
    if not owner.email or not owner.is_active:
        return False
    values = {
        "full_name": display_name(owner), "request_id": request.id,
        "form_label": FORM_TYPES.get(request.form_type, {}).get("label", request.form_type),
        "customer_name": request.data.get("customer_name") or "—", "reviewer": display_name(reviewer_user),
        "link": f"{settings.public_url.rstrip('/')}/sales/my_requests" + ("" if approved else "?tab=returned"),
    }
    try:
        if approved:
            mail.send(owner.email, *mail.compose("request_approved", **values))
        else:
            mail.send(owner.email, *mail.compose("request_returned", reason=request.returned_reason, **values))
        return True
    except mail.MailError:
        return False


def daftra_failed(request: Request, user: User, audit: Audit, db: Session, message: str, code: int) -> HTTPException:
    """Saves why the Daftra documents could not all be created, with the ids of those that were."""
    request.daftra_error = message
    audit.log(user, "request.daftra_failed", "request", request.id, request_label(request), after={"error": message})
    try:
        db.commit()
    except Exception:
        # The fault left the session unusable (a database error); nothing more can be saved now
        log.exception("Could not save the Daftra failure of request %s", request.id)
        db.rollback()
    return HTTPException(code, message)


@router.post("/review/requests/{request_id}/approve")
def approve(request_id: int, body: DecisionIn, user: User = Depends(reviewer), db: Session = Depends(get_db),
            audit: Audit = Depends()):
    # Held until the commit, so two managers approving at once cannot both create the Daftra documents
    db.execute(select(Request.id).where(Request.id == request_id).with_for_update())
    request = reviewable(request_id, body, user, db)
    daftra_summary = {}
    if FORM_TYPES.get(request.form_type, {}).get("invoiced"):
        try:
            daftra_summary = daftra_sync.sync(request, db, user)
        except daftra_sync.SyncError as error:
            # The request stays submitted; what was created so far is kept, so approving again carries on
            raise daftra_failed(request, user, audit, db, str(error),
                                status.HTTP_502_BAD_GATEWAY if error.from_daftra else status.HTTP_409_CONFLICT)
        except Exception as error:
            # A fault of ours midway: still keep the ids of what Daftra already created
            log.exception("Creating the Daftra documents of request %s failed", request.id)
            raise daftra_failed(request, user, audit, db, f"خطأ غير متوقع أثناء الإنشاء في دفترة: {error}",
                                status.HTTP_500_INTERNAL_SERVER_ERROR) from error
    request.status = "approved"
    request.returned_reason = None
    request.reviewed_by = user
    request.reviewed_at = datetime.now(timezone.utc)
    add_event(db, request, user, "approved")
    db.flush()
    emailed = notify_owner(request, user, approved=True)
    audit.log(user, "request.approve", "request", request.id, request_label(request),
              after={"status": "approved", "email_sent": emailed, **daftra_summary})
    db.commit()
    return review_out(request)


@router.post("/review/requests/{request_id}/return")
def return_request(request_id: int, body: ReturnIn, user: User = Depends(reviewer), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    reason = body.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "اكتب سبب الإعادة بوضوح ليعرف الموظف ما المطلوب تعديله")
    request = reviewable(request_id, body, user, db)
    request.status = "returned"
    request.returned_reason = reason
    request.reviewed_by = user
    request.reviewed_at = datetime.now(timezone.utc)
    add_event(db, request, user, "returned", reason)
    db.flush()
    emailed = notify_owner(request, user, approved=False)
    audit.log(user, "request.return", "request", request.id, request_label(request),
              after={"status": "returned", "reason": reason, "email_sent": emailed})
    db.commit()
    return review_out(request)
