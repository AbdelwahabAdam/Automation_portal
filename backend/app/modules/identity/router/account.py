"""The account page's routes. Transport only."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.context import Actor
from ....core.database import get_db
from ....core.security import acting, get_current_user
from ..models import User
from ..service import account

router = APIRouter(prefix="/api/account")


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)


class PasswordChangeIn(BaseModel):
    current_password: str
    # bcrypt reads at most 72 bytes of a password
    new_password: str = Field(min_length=8, max_length=72)


class CodeIn(BaseModel):
    code: str


class PasswordIn(BaseModel):
    password: str


def optional_two_step(user: User = Depends(get_current_user)) -> User:
    """The user, as long as two-step login is theirs to turn off."""
    return account.check_may_turn_off(user)


@router.get("")
def my_account(user: User = Depends(get_current_user)):
    return account.account_out(user)


@router.put("")
def update_profile(body: ProfileIn, who: Actor = Depends(acting(get_current_user)),
                   db: Session = Depends(get_db)):
    return account.rename(db, who, body.full_name)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChangeIn, who: Actor = Depends(acting(get_current_user)),
                    db: Session = Depends(get_db)):
    account.change_password(db, who, body.current_password, body.new_password)


@router.post("/mfa/send-code")
def send_enable_code(user: User = Depends(optional_two_step), db: Session = Depends(get_db)):
    return account.send_enable_code(db, user)


@router.post("/mfa/enable")
def enable_mfa(body: CodeIn, who: Actor = Depends(acting(optional_two_step)),
               db: Session = Depends(get_db)):
    return account.enable_two_step(db, who, body.code)


@router.post("/mfa/disable")
def disable_mfa(body: PasswordIn, who: Actor = Depends(acting(optional_two_step)),
                db: Session = Depends(get_db)):
    return account.disable_two_step(db, who, body.password)
