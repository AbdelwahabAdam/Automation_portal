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
def review_queue(user=Depends(reviewer), db: Session = Depends(get_db)):
    """The requests of the forms this user may see, newest first: those sent, and the employees'
    drafts (the «المسودات» tab, with a count per employee), a draft by when it was last saved."""
    return review.queue(db, user)


@router.post("/review/requests/{request_id}/approve")
def approve(request_id: int, body: schemas.DecisionIn, who: Actor = Depends(acting(reviewer)),
            db: Session = Depends(get_db)):
    return review.approve(db, who, request_id, body.revision)


@router.post("/review/requests/{request_id}/return")
def return_request(request_id: int, body: schemas.ReturnIn, who: Actor = Depends(acting(reviewer)),
                   db: Session = Depends(get_db)):
    return review.return_to_owner(db, who, request_id, body.revision, body.reason)
