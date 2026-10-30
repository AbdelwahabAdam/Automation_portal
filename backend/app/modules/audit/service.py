"""Writing activity-log entries, and reading them back for the page.

An entry is added to the same database session as the change it describes, so the caller's
commit saves both together and no change is saved without its entry.
"""

from fastapi import Depends
from fastapi import Request as HttpRequest
from sqlalchemy.orm import Session

from ...core.context import Actor
from ...core.database import get_db
from .models import AuditLog


# Set by identity at import. audit must not import identity: every module writes to the activity
# log, so audit sits below them all and nothing it needs may point back up.
_list_users = None


def set_user_lister(lister):
    """identity says how to list the users the activity-log filter offers."""
    global _list_users
    _list_users = lister


def users_for_filter(db: Session) -> list[dict]:
    return _list_users(db) if _list_users else []


def changes(before: dict, after: dict) -> tuple[dict, dict]:
    """Keeps only the keys whose value differs between the two."""
    changed = [key for key in before.keys() | after.keys() if before.get(key) != after.get(key)]
    return {k: before[k] for k in changed if k in before}, {k: after[k] for k in changed if k in after}


def log(db: Session, who: Actor, action: str, entity_type: str = "", entity_id: int | None = None,
        entity_label: str = "", before: dict | None = None, after: dict | None = None,
        username: str = ""):
    """Adds one entry to the caller's session; the caller commits it with the change itself."""
    user = who.user
    db.add(AuditLog(
        user_id=user.id if user is not None else None,
        username=(user.username if user is not None else (username or who.username))[:50],
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label[:160],
        before=before or None,
        after=after or None,
        ip=who.ip,
        user_agent=who.user_agent,
    ))


class Audit:
    """Request-scoped writer: knows the caller's address and shares the endpoint's session.

    A route takes one with `Depends()`; a job calls `log` with `Actor.system()` instead.
    """

    def __init__(self, http_request: HttpRequest, db: Session = Depends(get_db)):
        self.db = db
        self.ip = http_request.client.host if http_request.client else ""
        self.user_agent = (http_request.headers.get("user-agent") or "")[:300]

    def actor(self, user=None, username: str = "") -> Actor:
        return Actor(user=user, ip=self.ip, user_agent=self.user_agent,
                     username=getattr(user, "username", "") or username)

    def log(self, actor, action: str, entity_type: str = "", entity_id: int | None = None,
            entity_label: str = "", before: dict | None = None, after: dict | None = None,
            username: str = ""):
        log(self.db, self.actor(actor, username), action, entity_type, entity_id, entity_label,
            before, after, username)
