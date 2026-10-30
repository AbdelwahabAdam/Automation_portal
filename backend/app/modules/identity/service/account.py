"""My account: the signed-in user's own name, password and two-step login."""

from sqlalchemy.orm import Session

from ....core.config import settings
from ....core.context import Actor
from ....core.errors import Conflict, Forbidden, Invalid, TooManyRequests, Unavailable
from ....core.security import hash_password, verify_password
from ... import notifications
from ...audit import log as audit_log
from .. import mfa
from ..models import User


def account_out(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_admin": user.is_admin,
        "roles": [role.name for role in user.roles],
        "mfa_enabled": mfa.applies(user),
        # Admins cannot turn two-step login off
        "mfa_required": settings.require_admin_mfa and user.is_admin,
    }


def check_password(user: User, password: str):
    # Forbidden, not Unauthorized: a wrong password here must not end the session
    if not user.password_hash or not verify_password(password, user.password_hash):
        raise Forbidden("كلمة المرور الحالية غير صحيحة")


def check_may_turn_off(user: User) -> User:
    if settings.require_admin_mfa and user.is_admin:
        raise Conflict("التحقق بخطوتين إلزامي لمدير النظام")
    return user


def rename(db: Session, who: Actor, full_name: str) -> dict:
    user = who.user
    name = full_name.strip()
    if not name:
        raise Invalid("اكتب الاسم")
    if name != user.full_name:
        audit_log(db, who, "account.update", "user", user.id, user.username,
                  before={"full_name": user.full_name}, after={"full_name": name})
        user.full_name = name
        db.commit()
    return account_out(user)


def change_password(db: Session, who: Actor, current_password: str, new_password: str):
    user = who.user
    check_password(user, current_password)
    user.password_hash = hash_password(new_password)
    audit_log(db, who, "account.password_change", "user", user.id, user.username)
    db.commit()


def send_enable_code(db: Session, user: User) -> dict:
    """First step of turning two-step login on: proves the user receives email at their address."""
    if user.mfa_enabled:
        raise Conflict("التحقق بخطوتين مفعّل بالفعل")
    if not user.email:
        raise Conflict("لا يوجد بريد إلكتروني لحسابك. اطلب من مدير النظام إضافته أولًا.")
    wait = mfa.seconds_until_resend(user)
    if wait:
        raise TooManyRequests(f"أُرسل رمز قبل قليل. انتظر {wait} ثانية قبل طلب رمز جديد.")
    code = mfa.new_code(user)
    try:
        notifications.send_login_code(user.email, user.full_name, code, mfa.CODE_MINUTES)
    except notifications.MailError:
        raise Unavailable("تعذر إرسال البريد الآن. حاول لاحقًا.")
    db.commit()
    return {"email_hint": mfa.mask_email(user.email)}


def enable_two_step(db: Session, who: Actor, code: str) -> dict:
    user = who.user
    if user.mfa_enabled:
        raise Conflict("التحقق بخطوتين مفعّل بالفعل")
    if not mfa.check_code(user, code):
        # The attempt itself is kept, which is what makes the tries run out
        db.commit()
        raise Invalid("الرمز غير صحيح أو انتهت صلاحيته")
    user.mfa_enabled = True
    audit_log(db, who, "account.mfa_enabled", "user", user.id, user.username)
    db.commit()
    return account_out(user)


def disable_two_step(db: Session, who: Actor, password: str) -> dict:
    user = who.user
    if not user.mfa_enabled:
        raise Conflict("التحقق بخطوتين غير مفعّل")
    check_password(user, password)
    user.mfa_enabled = False
    mfa.clear_code(user)
    audit_log(db, who, "account.mfa_disabled", "user", user.id, user.username)
    db.commit()
    return account_out(user)
