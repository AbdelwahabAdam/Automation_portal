"""Admin pages: users, roles (lists of pages) and the audit log."""

import csv
import io
import json
import re
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .audit import ACTIONS, ENTITY_TYPES, FIELD_LABELS, VALUE_LABELS, Audit, changes, role_snapshot, user_snapshot
from . import daftra, mail, mfa
from .config import settings
from .database import get_db
from .models import AuditLog, Request, Role, User
from .pages import ADMIN_DEPARTMENT, ASSIGNABLE_PAGE_KEYS, DEPARTMENT_LABELS, MANAGEABLE_DEPARTMENTS, navigation
from .security import create_password_link, require_admin
from .text import UAE

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

# No "@" in a username, so a login name can never be mistaken for an email
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,50}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EXPORT_LIMIT = 20000


# ---------- Roles ----------

class RoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    pages: list[str]


class RoleOut(BaseModel):
    id: int
    name: str
    pages: list[str]
    user_count: int


def role_out(role: Role) -> RoleOut:
    return RoleOut(id=role.id, name=role.name, pages=role.pages, user_count=len(role.users))


def clean_role(body: RoleIn, db: Session, current: Role | None = None) -> tuple[str, list[str]]:
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اكتب اسم الدور")
    taken = db.scalar(select(Role).where(func.lower(Role.name) == name.lower()))
    if taken is not None and taken is not current:
        raise HTTPException(status.HTTP_409_CONFLICT, "يوجد دور بنفس الاسم")
    # Kept in page order; unknown and admin-only keys are dropped
    return name, [key for key in ASSIGNABLE_PAGE_KEYS if key in set(body.pages)]


def existing_role(role_id: int, db: Session = Depends(get_db)) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الدور غير موجود")
    return role


@router.get("/pages")
def assignable_pages():
    """The pages that can be put in a role, grouped by department."""
    return [d for d in navigation(ASSIGNABLE_PAGE_KEYS) if d["key"] != ADMIN_DEPARTMENT]


@router.get("/departments")
def manageable_departments():
    """The departments a user can be made manager of."""
    return [{"key": key, "label": DEPARTMENT_LABELS[key]} for key in MANAGEABLE_DEPARTMENTS]


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db)):
    roles = db.scalars(select(Role).options(selectinload(Role.users)).order_by(Role.name))
    return [role_out(role) for role in roles]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(body: RoleIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                audit: Audit = Depends()):
    name, pages = clean_role(body, db)
    role = Role(name=name, pages=pages)
    db.add(role)
    db.flush()
    audit.log(admin, "role.create", "role", role.id, role.name, after=role_snapshot(role))
    db.commit()
    return role_out(role)


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(body: RoleIn, role: Role = Depends(existing_role), admin: User = Depends(require_admin),
                db: Session = Depends(get_db), audit: Audit = Depends()):
    before = role_snapshot(role)
    role.name, role.pages = clean_role(body, db, role)
    old, new = changes(before, role_snapshot(role))
    if new:
        audit.log(admin, "role.update", "role", role.id, role.name, old, new)
    db.commit()
    return role_out(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role: Role = Depends(existing_role), admin: User = Depends(require_admin),
                db: Session = Depends(get_db), audit: Audit = Depends()):
    if role.users:
        raise HTTPException(status.HTTP_409_CONFLICT, "الدور مُسند لمستخدمين؛ أزله عنهم أولًا")
    audit.log(admin, "role.delete", "role", role.id, role.name, before=role_snapshot(role))
    db.delete(role)
    db.commit()


# ---------- Users ----------

class RoleRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    is_admin: bool
    is_active: bool
    # False until an invited user has set a password
    has_password: bool
    # Logs in with an emailed code after the password: every admin, and users who turned it on
    two_step: bool
    manages: list[str]
    daftra_staff_id: int | None
    created_at: datetime
    roles: list[RoleRef]


class InviteOut(BaseModel):
    user: AdminUserOut
    email_sent: bool
    # Given to the admin to pass on by hand, only when the email could not be sent
    link: str | None


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    role_ids: list[int] = []
    manages: list[str] = []
    is_admin: bool = False
    daftra_staff_id: int | None = None


class UserUpdate(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    role_ids: list[int]
    manages: list[str] = []
    is_admin: bool
    is_active: bool
    daftra_staff_id: int | None = None


def clean_manages(keys: list[str]) -> list[str]:
    return [key for key in MANAGEABLE_DEPARTMENTS if key in set(keys)]


def clean_email(raw: str, db: Session, current: User | None = None) -> str:
    email = raw.strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اكتب بريدًا إلكترونيًا صحيحًا")
    taken = db.scalar(select(User).where(User.email == email))
    if taken is not None and taken is not current:
        raise HTTPException(status.HTTP_409_CONFLICT, "البريد الإلكتروني مستخدم لحساب آخر")
    return email


def send_password_link(user: User, admin: User, audit: Audit) -> InviteOut:
    """Emails the user a link to set their password; falls back to handing the link to the admin."""
    link = create_password_link(user)
    try:
        mail.send_password_link(user.email, user.full_name, user.username, link, settings.password_link_hours,
                                invited=not user.has_password)
        sent = True
    except mail.MailError:
        sent = False
    audit.log(admin, "user.invite", "user", user.id, user.username, after={"email": user.email, "email_sent": sent})
    return InviteOut(user=AdminUserOut.model_validate(user), email_sent=sent, link=None if sent else link)


def roles_by_id(role_ids: list[int], db: Session) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.id.in_(role_ids))).all() if role_ids else []
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "أحد الأدوار المختارة غير موجود")
    return list(roles)


def existing_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "المستخدم غير موجود")
    return user


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).options(selectinload(User.roles)).order_by(User.is_active.desc(), User.username)).all()


@router.get("/daftra/staff")
def daftra_staff_members():
    """Daftra's active staff with ids, to link a portal user to the staff member on their invoices."""
    try:
        return daftra.list_staff_members()
    except daftra.DaftraError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "تعذر تحميل الموظفين من دفترة")


@router.post("/users", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                audit: Audit = Depends()):
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "اسم المستخدم من 3 إلى 50 حرفًا: حروف إنجليزية صغيرة وأرقام ونقطة وشرطة فقط",
        )
    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "اسم المستخدم مستخدم من قبل")
    user = User(
        username=username, email=clean_email(body.email, db), full_name=body.full_name.strip(),
        is_admin=body.is_admin, roles=roles_by_id(body.role_ids, db), manages=clean_manages(body.manages),
        daftra_staff_id=body.daftra_staff_id,
    )
    db.add(user)
    db.flush()
    audit.log(admin, "user.create", "user", user.id, user.username, after=user_snapshot(user))
    invite = send_password_link(user, admin, audit)
    db.commit()
    return invite


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(body: UserUpdate, user: User = Depends(existing_user), admin: User = Depends(require_admin),
                db: Session = Depends(get_db), audit: Audit = Depends()):
    # An admin cannot lock themselves out, so there is always at least one working admin
    if user.id == admin.id and not (body.is_admin and body.is_active):
        raise HTTPException(status.HTTP_409_CONFLICT, "لا يمكنك إيقاف حسابك أو إزالة صلاحية المدير عن نفسك")
    before = user_snapshot(user)
    user.email = clean_email(body.email, db, user)
    user.full_name = body.full_name.strip()
    user.is_admin = body.is_admin
    user.is_active = body.is_active
    user.roles = roles_by_id(body.role_ids, db)
    user.manages = clean_manages(body.manages)
    user.daftra_staff_id = body.daftra_staff_id
    old, new = changes(before, user_snapshot(user))
    if new:
        audit.log(admin, "user.update", "user", user.id, user.username, old, new)
    db.commit()
    return user


@router.post("/users/{user_id}/invite", response_model=InviteOut)
def invite_user(user: User = Depends(existing_user), admin: User = Depends(require_admin),
                db: Session = Depends(get_db), audit: Audit = Depends()):
    """Sends the invitation again, or a link to set a new password for a user who already has one."""
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "الحساب موقوف؛ فعّله أولًا")
    if not user.email:
        raise HTTPException(status.HTTP_409_CONFLICT, "أضف بريدًا إلكترونيًا للمستخدم أولًا")
    invite = send_password_link(user, admin, audit)
    db.commit()
    return invite


@router.post("/users/{user_id}/mfa-reset", response_model=AdminUserOut)
def reset_mfa(user: User = Depends(existing_user), admin: User = Depends(require_admin),
              db: Session = Depends(get_db), audit: Audit = Depends()):
    """Turns off the two-step login a user chose for themselves. It cannot be turned off for an admin."""
    if settings.require_admin_mfa and user.is_admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "التحقق بخطوتين إلزامي لمدير النظام")
    if not user.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "التحقق بخطوتين غير مفعّل لهذا المستخدم")
    user.mfa_enabled = False
    mfa.clear_code(user)
    audit.log(admin, "user.mfa_reset", "user", user.id, user.username)
    db.commit()
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user: User = Depends(existing_user), admin: User = Depends(require_admin),
                db: Session = Depends(get_db), audit: Audit = Depends()):
    if user.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "لا يمكنك حذف حسابك")
    # A request must keep its owner, so a user who has any is stopped rather than deleted
    if db.scalar(select(func.count()).select_from(Request).where(Request.created_by_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "لهذا المستخدم طلبات مسجلة باسمه فلا يمكن حذفه. أوقف حسابه بدلًا من ذلك.")
    audit.log(admin, "user.delete", "user", user.id, user.username, before=user_snapshot(user))
    db.delete(user)
    db.commit()


# ---------- Mail test ----------

class MailTestIn(BaseModel):
    template: str
    to: str


def known_email(name: str) -> str:
    if name not in mail.EMAILS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قالب البريد غير معروف")
    return name


@router.get("/mail")
def mail_settings(admin: User = Depends(require_admin)):
    """The emails that can be tested and where they are sent from. The password is never included."""
    return {
        "templates": [{"key": key, "label": email["label"]} for key, email in mail.EMAILS.items()],
        "configured": mail.is_configured(),
        "server": f"{settings.smtp_host}:{settings.smtp_port}" if settings.smtp_host else "",
        "sender": settings.mail_from,
        "default_to": admin.email or "",
    }


@router.get("/mail/preview/{name}")
def preview_mail(name: str = Depends(known_email), admin: User = Depends(require_admin)):
    subject, _, html = mail.compose_sample(name, admin.email or "name@example.com", admin.full_name or admin.username)
    return {"subject": subject, "html": html}


@router.post("/mail/test", status_code=status.HTTP_204_NO_CONTENT)
def send_test_mail(body: MailTestIn, admin: User = Depends(require_admin), db: Session = Depends(get_db),
                   audit: Audit = Depends()):
    """Sends one email with made-up values, to check the mail settings and how a template looks in an inbox."""
    name = known_email(body.template)
    to = body.to.strip().lower()
    if len(to) > 254 or not EMAIL_RE.match(to):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "اكتب بريدًا إلكترونيًا صحيحًا")
    error = None
    try:
        mail.send(to, *mail.compose_sample(name, to, admin.full_name or admin.username))
    except mail.MailError as failure:
        error = str(failure)
    audit.log(admin, "mail.test", after={"template": name, "email": to, "email_sent": error is None})
    db.commit()
    if error:
        # The mail server's own words, since this page exists to diagnose the mail settings
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"تعذر الإرسال. رد خادم البريد: {error}")


# ---------- Audit log ----------

class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    user_id: int | None
    username: str
    action: str
    entity_type: str
    entity_id: int | None
    entity_label: str
    before: dict | None
    after: dict | None
    ip: str
    user_agent: str


class AuditPage(BaseModel):
    total: int
    items: list[AuditOut]


def audit_filters(user_id: int | None = None, action: str = "", entity_type: str = "",
                  date_from: date | None = None, date_to: date | None = None, search: str = "") -> list:
    conditions = []
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if date_from:
        conditions.append(AuditLog.at >= datetime.combine(date_from, time.min, UAE))
    if date_to:
        conditions.append(AuditLog.at < datetime.combine(date_to + timedelta(days=1), time.min, UAE))
    if search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(AuditLog.entity_label.ilike(pattern) | AuditLog.username.ilike(pattern))
    return conditions


@router.get("/audit/options")
def audit_options(db: Session = Depends(get_db)):
    """The lists behind the audit log filters and the labels used to display an entry."""
    users = db.execute(select(User.id, User.username, User.full_name).order_by(User.username)).all()
    return {
        "actions": ACTIONS,
        "entity_types": ENTITY_TYPES,
        "field_labels": FIELD_LABELS,
        "value_labels": VALUE_LABELS,
        "users": [{"id": u.id, "username": u.username, "full_name": u.full_name} for u in users],
    }


@router.get("/audit", response_model=AuditPage)
def list_audit(conditions: list = Depends(audit_filters), limit: int = 50, offset: int = 0,
               db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    items = db.scalars(
        select(AuditLog).where(*conditions).order_by(AuditLog.id.desc()).limit(limit).offset(max(0, offset))
    ).all()
    return {"total": total, "items": items}


@router.get("/audit/export")
def export_audit(conditions: list = Depends(audit_filters), admin: User = Depends(require_admin),
                 db: Session = Depends(get_db), audit: Audit = Depends()):
    """The filtered log as a CSV file that Excel opens directly."""
    entries = db.scalars(
        select(AuditLog).where(*conditions).order_by(AuditLog.id.desc()).limit(EXPORT_LIMIT)
    ).all()

    def values(data: dict | None) -> str:
        if not data:
            return ""
        return json.dumps({FIELD_LABELS.get(k, k): v for k, v in data.items()}, ensure_ascii=False)

    def cell(value: str) -> str:
        # Excel would run a cell starting with one of these as a formula
        return "'" + value if value[:1] in ("=", "+", "-", "@") else value

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["الوقت (توقيت الإمارات)", "المستخدم", "الإجراء", "نوع السجل", "السجل",
                     "القيم قبل", "القيم بعد", "عنوان IP", "المتصفح"])
    for entry in entries:
        writer.writerow([
            entry.at.astimezone(UAE).strftime("%Y-%m-%d %H:%M:%S"), cell(entry.username),
            ACTIONS.get(entry.action, entry.action), ENTITY_TYPES.get(entry.entity_type, entry.entity_type),
            cell(entry.entity_label), values(entry.before), values(entry.after), entry.ip, cell(entry.user_agent),
        ])
    audit.log(admin, "audit.export", after={"rows": len(entries)})
    db.commit()
    # The BOM makes Excel read the file as UTF-8
    return Response(
        "﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
