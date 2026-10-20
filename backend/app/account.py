"""My account: the signed-in user's own name, password and two-step login."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import mail, mfa
from .audit import Audit
from .config import settings
from .database import get_db
from .models import User
from .pages import DEPARTMENT_LABELS
from .security import get_current_user, hash_password, verify_password

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


def account_out(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_admin": user.is_admin,
        "roles": [role.name for role in user.roles],
        "manages": [DEPARTMENT_LABELS[key] for key in user.manages if key in DEPARTMENT_LABELS],
        "mfa_enabled": mfa.applies(user),
        # Admins cannot turn two-step login off
        "mfa_required": settings.require_admin_mfa and user.is_admin,
    }


def check_password(user: User, password: str):
    # 403, not 401: a wrong password here must not end the session
    if not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "كلمة المرور الحالية غير صحيحة")


def optional_two_step(user: User = Depends(get_current_user)) -> User:
    if settings.require_admin_mfa and user.is_admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "التحقق بخطوتين إلزامي لمدير النظام")
    return user


@router.get("")
def my_account(user: User = Depends(get_current_user)):
    return account_out(user)


@router.put("")
def update_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    name = body.full_name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "اكتب الاسم")
    if name != user.full_name:
        audit.log(user, "account.update", "user", user.id, user.username,
                  before={"full_name": user.full_name}, after={"full_name": name})
        user.full_name = name
        db.commit()
    return account_out(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db),
                    audit: Audit = Depends()):
    check_password(user, body.current_password)
    user.password_hash = hash_password(body.new_password)
    audit.log(user, "account.password_change", "user", user.id, user.username)
    db.commit()


@router.post("/mfa/send-code")
def send_enable_code(user: User = Depends(optional_two_step), db: Session = Depends(get_db)):
    """First step of turning two-step login on: proves the user receives email at their address."""
    if user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "التحقق بخطوتين مفعّل بالفعل")
    if not user.email:
        raise HTTPException(status.HTTP_409_CONFLICT, "لا يوجد بريد إلكتروني لحسابك. اطلب من مدير النظام إضافته أولًا.")
    wait = mfa.seconds_until_resend(user)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"أُرسل رمز قبل قليل. انتظر {wait} ثانية قبل طلب رمز جديد.")
    code = mfa.new_code(user)
    try:
        mail.send_login_code(user.email, user.full_name, code, mfa.CODE_MINUTES)
    except mail.MailError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "تعذر إرسال البريد الآن. حاول لاحقًا.")
    db.commit()
    return {"email_hint": mfa.mask_email(user.email)}


@router.post("/mfa/enable")
def enable_mfa(body: CodeIn, user: User = Depends(optional_two_step), db: Session = Depends(get_db),
               audit: Audit = Depends()):
    if user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "التحقق بخطوتين مفعّل بالفعل")
    if not mfa.check_code(user, body.code):
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "الرمز غير صحيح أو انتهت صلاحيته")
    user.mfa_enabled = True
    audit.log(user, "account.mfa_enabled", "user", user.id, user.username)
    db.commit()
    return account_out(user)


@router.post("/mfa/disable")
def disable_mfa(body: PasswordIn, user: User = Depends(optional_two_step), db: Session = Depends(get_db),
                audit: Audit = Depends()):
    if not user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "التحقق بخطوتين غير مفعّل")
    check_password(user, body.password)
    user.mfa_enabled = False
    mfa.clear_code(user)
    audit.log(user, "account.mfa_disabled", "user", user.id, user.username)
    db.commit()
    return account_out(user)
