"""The queries on the activity log. No commits, no decisions."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.text import UAE
from .models import AuditLog


def filters(user_id: int | None = None, action: str = "", entity_type: str = "",
            date_from: date | None = None, date_to: date | None = None, search: str = "") -> list:
    """The conditions behind the page's filter boxes."""
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


def times_since(db: Session, action: str, since: datetime, username: str) -> int:
    """How often this action was recorded for that name since then — e.g. failed logins."""
    return db.scalar(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.action == action, AuditLog.username == username, AuditLog.at > since,
        )
    )


def happened_since(db: Session, action: str, since: datetime, user_id: int, flag: str = "") -> bool:
    """Whether this action was recorded for that user since then, optionally only where `flag`
    was true in the entry's values — e.g. a password-reset email that did go out."""
    conditions = [AuditLog.user_id == user_id, AuditLog.action == action, AuditLog.at > since]
    if flag:
        conditions.append(AuditLog.after[flag].as_boolean())
    return bool(db.scalar(select(AuditLog.id).where(*conditions).limit(1)))


def count(db: Session, conditions: list) -> int:
    return db.scalar(select(func.count()).select_from(AuditLog).where(*conditions))


def page(db: Session, conditions: list, limit: int, offset: int) -> list[AuditLog]:
    return list(db.scalars(
        select(AuditLog).where(*conditions).order_by(AuditLog.id.desc()).limit(limit).offset(offset)
    ))
