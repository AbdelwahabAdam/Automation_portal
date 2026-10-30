"""The users screen: adding a user, changing one, inviting them, and stopping an account."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ....core.config import settings
from ....core.context import Actor
from ....core.errors import Conflict, Invalid, NotFound
from ... import notifications, requests
from ...audit import changes
from ...audit import log as audit_log
from .. import mfa
from ..models import Role, User
from ..passwords import create_password_link
from ..snapshots import user_snapshot

# No "@" in a username, so a login name can never be mistaken for an email
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,50}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL = 254


def listed(db: Session) -> list[User]:
    return list(db.scalars(
        select(User).options(selectinload(User.roles)).order_by(User.is_active.desc(), User.username)
    ))


def by_id(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("المستخدم غير موجود")
    return user


def clean_email(db: Session, raw: str, current: User | None = None) -> str:
    email = raw.strip().lower()
    if len(email) > MAX_EMAIL or not EMAIL_RE.match(email):
        raise Invalid("اكتب بريدًا إلكترونيًا صحيحًا")
    taken = db.scalar(select(User).where(User.email == email))
    if taken is not None and taken is not current:
        raise Conflict("البريد الإلكتروني مستخدم لحساب آخر")
    return email


def roles_by_id(db: Session, role_ids: list[int]) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.id.in_(role_ids))).all() if role_ids else []
    if len(roles) != len(set(role_ids)):
        raise Invalid("أحد الأدوار المختارة غير موجود")
    return list(roles)


def send_password_link(db: Session, who: Actor, user: User) -> tuple[User, bool, str | None]:
    """Emails the user a link to set their password; falls back to handing the link to the admin."""
    link = create_password_link(user)
    try:
        notifications.send_password_link(user.email, user.full_name, user.username, link,
                                         settings.password_link_hours, invited=not user.has_password)
        sent = True
    except notifications.MailError:
        sent = False
    audit_log(db, who, "user.invite", "user", user.id, user.username,
              after={"email": user.email, "email_sent": sent})
    return user, sent, None if sent else link


def create(db: Session, who: Actor, body) -> tuple[User, bool, str | None]:
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise Invalid("اسم المستخدم من 3 إلى 50 حرفًا: حروف إنجليزية صغيرة وأرقام ونقطة وشرطة فقط")
    if db.scalar(select(User).where(User.username == username)) is not None:
        raise Conflict("اسم المستخدم مستخدم من قبل")
    user = User(
        username=username, email=clean_email(db, body.email), full_name=body.full_name.strip(),
        is_admin=body.is_admin, roles=roles_by_id(db, body.role_ids),
        daftra_staff_id=body.daftra_staff_id,
    )
    db.add(user)
    db.flush()
    audit_log(db, who, "user.create", "user", user.id, user.username, after=user_snapshot(user))
    invite = send_password_link(db, who, user)
    db.commit()
    return invite


def update(db: Session, who: Actor, user: User, body) -> User:
    admin = who.user
    # An admin cannot lock themselves out, so there is always at least one working admin
    if user.id == admin.id and not (body.is_admin and body.is_active):
        raise Conflict("لا يمكنك إيقاف حسابك أو إزالة صلاحية المدير عن نفسك")
    before = user_snapshot(user)
    user.email = clean_email(db, body.email, user)
    user.full_name = body.full_name.strip()
    user.is_admin = body.is_admin
    user.is_active = body.is_active
    user.roles = roles_by_id(db, body.role_ids)
    user.daftra_staff_id = body.daftra_staff_id
    old, new = changes(before, user_snapshot(user))
    if new:
        audit_log(db, who, "user.update", "user", user.id, user.username, old, new)
    db.commit()
    return user


def invite_again(db: Session, who: Actor, user: User) -> tuple[User, bool, str | None]:
    """Sends the invitation again, or a link to set a new password for a user who already has one."""
    if not user.is_active:
        raise Conflict("الحساب موقوف؛ فعّله أولًا")
    if not user.email:
        raise Conflict("أضف بريدًا إلكترونيًا للمستخدم أولًا")
    invite = send_password_link(db, who, user)
    db.commit()
    return invite


def reset_two_step(db: Session, who: Actor, user: User) -> User:
    """Turns off the two-step login a user chose for themselves. It cannot be turned off for an admin."""
    if settings.require_admin_mfa and user.is_admin:
        raise Conflict("التحقق بخطوتين إلزامي لمدير النظام")
    if not user.mfa_enabled:
        raise Conflict("التحقق بخطوتين غير مفعّل لهذا المستخدم")
    user.mfa_enabled = False
    mfa.clear_code(user)
    audit_log(db, who, "user.mfa_reset", "user", user.id, user.username)
    db.commit()
    return user


def delete(db: Session, who: Actor, user: User):
    if user.id == who.user.id:
        raise Conflict("لا يمكنك حذف حسابك")
    # A request must keep its owner, so a user who has any is stopped rather than deleted
    if requests.count_by_owner(db, user.id):
        raise Conflict("لهذا المستخدم طلبات مسجلة باسمه فلا يمكن حذفه. أوقف حسابه بدلًا من ذلك.")
    audit_log(db, who, "user.delete", "user", user.id, user.username, before=user_snapshot(user))
    db.delete(user)
    db.commit()
