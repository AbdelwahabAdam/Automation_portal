"""The queries on identity's own tables. No commits, no decisions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User


def active_by_id(db: Session, user_id: int) -> User | None:
    """The signed-in user a token names; None if there is no such user or it is switched off.
    This is what `core.security` is given as its loader."""
    user = db.get(User, user_id)
    return user if user is not None and user.is_active else None


def listed_users(db: Session) -> list[dict]:
    """Every user, for the activity-log filter: who there is to filter by."""
    rows = db.execute(select(User.id, User.username, User.full_name).order_by(User.username)).all()
    return [{"id": row.id, "username": row.username, "full_name": row.full_name} for row in rows]


def by_login(db: Session, identifier: str) -> User | None:
    """The user with this email or username. Usernames never contain "@", so the two cannot clash."""
    identifier = identifier.strip().lower()
    if not identifier:
        return None
    column = User.email if "@" in identifier else User.username
    return db.scalar(select(User).where(column == identifier))
