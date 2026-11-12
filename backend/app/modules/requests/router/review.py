"""The review queue and the two decisions. Transport only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.permissions import REVIEW, VIEW
from ....core.security import acting, require_any_form
from .. import schemas
from ..service import review

router = APIRouter(prefix="/api")
# Opening المراجعة takes view or review on at least one form; which requests show, and which can
# be decided on, is then checked form by form in the service.
reviewer = require_any_form(VIEW, REVIEW)


@router.get("/review/requests")
def review_queue(scope: str = "", user=Depends(reviewer), db: Session = Depends(get_db)):
    """The requests of the forms this user may see, newest first: those sent, and the employees'
    drafts (the «المسودات» tab, with a count per employee), a draft by when it was last saved.

    scope=review narrows it to the forms they may decide on, for the lists opened from لوحة المتابعة.
    """
    return review.queue(db, user, scope)


@router.post("/review/requests/{request_id}/approve")
def approve(request_id: int, body: schemas.DecisionIn, who: Actor = Depends(acting(reviewer)),
            db: Session = Depends(get_db)):
    return review.approve(db, who, request_id, body.revision)


@router.post("/review/requests/{request_id}/return")
def return_request(request_id: int, body: schemas.ReturnIn, who: Actor = Depends(acting(reviewer)),
                   db: Session = Depends(get_db)):
    return review.return_to_owner(db, who, request_id, body.revision, body.reason)


@router.post("/review/requests/{request_id}/delete")
def delete_request(request_id: int, body: schemas.DeleteIn, who: Actor = Depends(acting(reviewer)),
                   db: Session = Depends(get_db)):
    """Deletes a request that has not been approved — a draft, one sent in, or one returned for
    corrections — with the reason why.

    Only a reviewer of that request's own form may; the request is then hidden from its owner
    and from المراجعة, and its owner is told by email.
    """
    return review.delete_request(db, who, request_id, body.reason)
