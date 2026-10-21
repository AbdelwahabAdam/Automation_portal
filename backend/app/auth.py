"""Logging in and out, the two-step code, and the links that set a password."""

from datetime import datetime, timedelta, timezone
from functools import cache

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import mail, mfa
from .audit import Audit
from .config import settings
from .database import get_db
from .models import AuditLog, User
from .pages import navigation
from .security import (create_password_link, create_token, get_current_user, hash_password, user_for_password_token,
                       verify_password)

router = APIRouter(prefix="/api/auth")

RESET_EMAIL_INTERVAL = timedelta(minutes=3)
# This many failed logins for one account within the window block further attempts until it passes
LOGIN_FAILURE_LIMIT = 8
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)


class LoginIn(BaseModel):
    # Email or username
    username: str
    password: str
    # The 6-digit code from the email, once the server has sent it
    code: str = ""


class ForgotIn(BaseModel):
    username: str


class SetPasswordIn(BaseModel):
    token: str
    # bcrypt reads at most 72 bytes of a password
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    is_admin: bool
    # Departments and pages this user can open, in menu order
    navigation: list[dict]


class LoginOut(BaseModel):
    # True, with no token, when the password was right and a code has been emailed
    mfa_required: bool = False
    # Where the code went, partly hidden, and how long before another can be sent
    email_hint: str | None = None
    resend_in: int | None = None
    access_token: str | None = None
    user: UserOut | None = None


def user_out(user: User) -> dict:
    return {"id": user.id, "username": user.username, "email": user.email, "full_name": user.full_name,
            "is_admin": user.is_admin, "navigation": navigation(user.pages)}


def find_login(identifier: str, db: Session) -> User | None:
    """The user with this email or username. Usernames never contain "@", so the two cannot clash."""
    identifier = identifier.strip().lower()
    if not identifier:
        return None
    column = User.email if "@" in identifier else User.username
    return db.scalar(select(User).where(column == identifier))


@cache
def _unused_hash() -> str:
    return hash_password("no account has this password")


def password_matches(user: User | None, password: str) -> bool:
    """Checks the password. Without an account to check against, a hash is still checked, so the
    answer takes as long and does not tell which names have an account."""
    if user is None or not user.password_hash:
        verify_password(password, _unused_hash())
        return False
    return verify_password(password, user.password_hash)


def recent_failures(name: str, db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "auth.login_failed", AuditLog.username == name,
            AuditLog.at > datetime.now(timezone.utc) - LOGIN_FAILURE_WINDOW,
        )
    )


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db), audit: Audit = Depends()):
    user = find_login(body.username, db)
    # Failures are counted under the account's username however the name was typed
    name = user.username if user else body.username.strip().lower()[:50]
    if recent_failures(name, db) >= LOGIN_FAILURE_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "محاولات دخول كثيرة. حاول مرة أخرى بعد 15 دقيقة.")

    def fail(message: str, reason: str):
        audit.log(None, "auth.login_failed", username=name, after={"reason": reason})
        db.commit()
        return HTTPException(status.HTTP_401_UNAUTHORIZED, message)

    if not password_matches(user, body.password) or not user.is_active:
        raise fail("بيانات الدخول غير صحيحة", "كلمة المرور أو الحساب")
    if mfa.applies(user):
        if not user.email:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "حسابك يتطلب رمز تحقق بالبريد ولا يوجد له بريد إلكتروني. تواصل مع مدير النظام.")
        if not body.code.strip():
            return send_login_code(user, db, audit)
        if not mfa.check_code(user, body.code):
            raise fail("رمز التحقق غير صحيح أو انتهت صلاحيته", "رمز التحقق بخطوتين")
    audit.log(user, "auth.login")
    db.commit()
    return {"access_token": create_token(user), "user": user_out(user)}


def send_login_code(user: User, db: Session, audit: Audit) -> dict:
    """Emails a new code, unless one went out within the last minute (asking again keeps that one)."""
    wait = mfa.seconds_until_resend(user)
    if not wait:
        code = mfa.new_code(user)
        try:
            mail.send_login_code(user.email, user.full_name, code, mfa.CODE_MINUTES)
        except mail.MailError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "تعذر إرسال رمز التحقق إلى بريدك الآن. حاول بعد قليل.")
        audit.log(user, "auth.mfa_code_sent")
        db.commit()
    return {"mfa_required": True, "email_hint": mfa.mask_email(user.email), "resend_in": wait or mfa.RESEND_SECONDS}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db), audit: Audit = Depends()):
    audit.log(user, "auth.logout")
    db.commit()


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(body: ForgotIn, db: Session = Depends(get_db), audit: Audit = Depends()):
    """Emails a link to set a new password. Answers the same whether or not the account exists."""
    user = find_login(body.username, db)
    sent = False
    # One email per account every few minutes, so the form cannot be used to flood an inbox
    recent = user is not None and db.scalar(
        select(AuditLog.id).where(
            AuditLog.user_id == user.id, AuditLog.action == "auth.password_reset_request",
            AuditLog.at > datetime.now(timezone.utc) - RESET_EMAIL_INTERVAL,
            AuditLog.after["email_sent"].as_boolean(),
        ).limit(1)
    )
    if user is not None and user.is_active and user.email and not recent:
        try:
            mail.send_password_link(user.email, user.full_name, user.username, create_password_link(user),
                                    settings.password_link_hours, invited=False)
            sent = True
        except mail.MailError:
            pass
    audit.log(user, "auth.password_reset_request", username=body.username.strip().lower(), after={"email_sent": sent})
    db.commit()


@router.get("/password-link")
def check_password_link(token: str, db: Session = Depends(get_db)):
    """Tells the set-password screen whose link this is, or that it is no longer valid."""
    user = user_for_password_token(token, db)
    return {"username": user.username, "full_name": user.full_name, "invited": not user.has_password}


@router.post("/set-password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(body: SetPasswordIn, db: Session = Depends(get_db), audit: Audit = Depends()):
    user = user_for_password_token(body.token, db)
    user.password_hash = hash_password(body.password)
    audit.log(user, "auth.password_set", "user", user.id, user.username)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)
