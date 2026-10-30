"""Logging in and out, the two-step code, and the links that set a password.

Transport only: read the input, call the service, return the answer.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.security import acting, caller, get_current_user
from .. import schemas
from ..models import User
from ..service import auth

router = APIRouter(prefix="/api/auth")


@router.post("/login", response_model=schemas.LoginOut)
def login(body: schemas.LoginIn, who: Actor = Depends(caller), db: Session = Depends(get_db)):
    return auth.log_in(db, who, body.username, body.password, body.code)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(who: Actor = Depends(acting(get_current_user)), db: Session = Depends(get_db)):
    auth.log_out(db, who)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(body: schemas.ForgotIn, who: Actor = Depends(caller), db: Session = Depends(get_db)):
    auth.request_password_link(db, who, body.username)


@router.get("/password-link")
def check_password_link(token: str, db: Session = Depends(get_db)):
    return auth.whose_password_link(db, token)


@router.post("/set-password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(body: schemas.SetPasswordIn, who: Actor = Depends(caller), db: Session = Depends(get_db)):
    auth.set_password(db, who, body.token, body.password)


@router.get("/me", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return auth.user_out(db, user)
