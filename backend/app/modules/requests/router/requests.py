"""A salesperson's requests: the forms list, their own requests, drafts and submitting.
Transport only."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.permissions import REVIEW, SUBMIT, VIEW
from ....core.security import acting, get_current_user
from ... import form_engine
from .. import schemas
from ..models import Request
from ..service import access, drafts, review

router = APIRouter(prefix="/api")


def own_draft(request_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> Request:
    return access.own_draft(db, request_id, user)


def own_unsent_draft(request_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> Request:
    return access.own_unsent_draft(db, request_id, user)


def viewable_request(request_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> Request:
    return access.viewable(db, request_id, user)


@router.get("/form-types")
def form_types(user=Depends(get_current_user)):
    """Every form this user may do anything with, and what they may do with it. A form nobody has
    granted them is not in the list at all."""
    out = []
    for spec in form_engine.all_forms():
        may = {f"may_{does}": form_engine.may(user, spec.key, does) for does in (SUBMIT, VIEW, REVIEW)}
        if any(may.values()):
            out.append(spec.as_api(may))
    return out


@router.get("/requests/mine", response_model=list[schemas.RequestOut])
def my_requests(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return drafts.mine(db, user)


@router.get("/requests/mine/counts")
def my_request_counts(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return drafts.my_counts(db, user)


@router.post("/requests", response_model=schemas.RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(body: schemas.RequestIn, who: Actor = Depends(acting(get_current_user)),
                   db: Session = Depends(get_db)):
    return drafts.create(db, who, body.form_type, body.data, body.action)


@router.get("/requests/{request_id}", response_model=schemas.RequestOut)
def get_request(request: Request = Depends(viewable_request)):
    return request


@router.put("/requests/{request_id}", response_model=schemas.RequestOut)
def update_request(body: schemas.RequestUpdate, request: Request = Depends(own_draft),
                   who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    return drafts.update(db, who, request, body.data, body.action)


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(request: Request = Depends(own_unsent_draft), who: Actor = Depends(acting(get_current_user)),
                 db: Session = Depends(get_db)):
    drafts.delete(db, who, request)


@router.get("/requests/{request_id}/history")
def request_history(request: Request = Depends(viewable_request)):
    return review.history(request)
