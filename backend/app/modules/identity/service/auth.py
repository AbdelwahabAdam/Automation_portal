"""Signing in and out, the two-step code, and the links that set a password.

No HTTP here: the errors say what went wrong and the handler in `main.py` turns each into the
status the routes answered before.
"""

from datetime import datetime, timedelta, timezone
from functools import cache

from sqlalchemy.orm import Session

from ....core.config import settings
from ....core.context import Actor
from ....core.errors import Forbidden, TooManyRequests, Unauthorized, Unavailable
from ....core.security import create_token, hash_password, verify_password
from ....core.permissions import navigation
from ... import notifications, requests
from ...audit import happened_since, times_since
from ...audit import log as audit_log
from .. import mfa, repo
from ..models import User
from ..passwords import create_password_link, user_for_password_token

RESET_EMAIL_INTERVAL = timedelta(minutes=3)
# This many failed logins for one account within the window block further attempts until it passes
LOGIN_FAILURE_LIMIT = 8
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)


def user_out(db: Session, user: User) -> dict:
    """The signed-in user as every screen reads them, with the menu they may open.

    Someone whose access was taken away still reaches طلباتي if they have requests of their own,
    so the menu asks `requests` whether they do.
    """
    owns_requests = requests.count_by_owner(db, user.id) > 0
    return {"id": user.id, "username": user.username, "email": user.email, "full_name": user.full_name,
            "is_admin": user.is_admin, "permissions": user.permissions,
            "navigation": navigation(user, owns_requests), "daftra_fake": settings.daftra_fake}


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
    """How many failed logins this account has had lately. The count lives in the activity log,
    which audit owns, so audit is asked for it."""
    since = datetime.now(timezone.utc) - LOGIN_FAILURE_WINDOW
    return times_since(db, "auth.login_failed", since, name)


def log_in(db: Session, who: Actor, username: str, password: str, code: str = "") -> dict:
    """The token and the user, or what the second step needs."""
    user = repo.by_login(db, username)
    # Failures are counted under the account's username however the name was typed
    name = user.username if user else username.strip().lower()[:50]
    if recent_failures(name, db) >= LOGIN_FAILURE_LIMIT:
        raise TooManyRequests("محاولات دخول كثيرة. حاول مرة أخرى بعد 15 دقيقة.")

    def fail(message: str, reason: str):
        audit_log(db, who, "auth.login_failed", username=name, after={"reason": reason})
        db.commit()
        return Unauthorized(message)

    if not password_matches(user, password) or not user.is_active:
        raise fail("بيانات الدخول غير صحيحة", "كلمة المرور أو الحساب")
    signed_in = who.replace_user(user)
    if mfa.applies(user):
        if not user.email:
            raise Forbidden("حسابك يتطلب رمز تحقق بالبريد ولا يوجد له بريد إلكتروني. تواصل مع مدير النظام.")
        if not code.strip():
            return send_login_code(db, signed_in, user)
        if not mfa.check_code(user, code):
            raise fail("رمز التحقق غير صحيح أو انتهت صلاحيته", "رمز التحقق بخطوتين")
    audit_log(db, signed_in, "auth.login")
    db.commit()
    return {"access_token": create_token(user), "user": user_out(db, user)}


def send_login_code(db: Session, who: Actor, user: User) -> dict:
    """Emails a new code, unless one went out within the last minute (asking again keeps that one)."""
    wait = mfa.seconds_until_resend(user)
    if not wait:
        code = mfa.new_code(user)
        try:
            notifications.send_login_code(user.email, user.full_name, code, mfa.CODE_MINUTES)
        except notifications.MailError:
            raise Unavailable("تعذر إرسال رمز التحقق إلى بريدك الآن. حاول بعد قليل.")
        audit_log(db, who, "auth.mfa_code_sent")
        db.commit()
    return {"mfa_required": True, "email_hint": mfa.mask_email(user.email), "resend_in": wait or mfa.RESEND_SECONDS}


def log_out(db: Session, who: Actor):
    audit_log(db, who, "auth.logout")
    db.commit()


def request_password_link(db: Session, who: Actor, username: str):
    """Emails a link to set a new password. Answers the same whether or not the account exists."""
    user = repo.by_login(db, username)
    sent = False
    # One email per account every few minutes, so the form cannot be used to flood an inbox
    recent = user is not None and happened_since(
        db, "auth.password_reset_request", datetime.now(timezone.utc) - RESET_EMAIL_INTERVAL,
        user.id, flag="email_sent",
    )
    if user is not None and user.is_active and user.email and not recent:
        try:
            notifications.send_password_link(user.email, user.full_name, user.username,
                                             create_password_link(user), settings.password_link_hours,
                                             invited=False)
            sent = True
        except notifications.MailError:
            pass
    acting = who.replace_user(user) if user is not None else who
    audit_log(db, acting, "auth.password_reset_request",
              username=username.strip().lower(), after={"email_sent": sent})
    db.commit()


def whose_password_link(db: Session, token: str) -> dict:
    """Tells the set-password screen whose link this is, or that it is no longer valid."""
    user = user_for_password_token(token, db)
    return {"username": user.username, "full_name": user.full_name, "invited": not user.has_password}


def set_password(db: Session, who: Actor, token: str, password: str):
    user = user_for_password_token(token, db)
    user.password_hash = hash_password(password)
    audit_log(db, who.replace_user(user), "auth.password_set", "user", user.id, user.username)
    db.commit()
