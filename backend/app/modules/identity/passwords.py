"""The links a user opens to set their password, for an invitation or a reset.

Single-use: the link carries a short hash of the current password, so setting one makes every
link issued before it invalid.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.errors import BadRequest
from ...core.security import ALGORITHM
from .models import User

USE = "set_password"


def _password_version(user: User) -> str:
    """Changes whenever the password does, which is what makes a password link single-use."""
    return hashlib.sha256(f"{user.id}:{user.password_hash or ''}".encode()).hexdigest()[:16]


def create_password_link(user: User) -> str:
    """A link the user opens to set their password, for an invitation or a reset."""
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.password_link_hours)
    token = jwt.encode(
        {"sub": str(user.id), "exp": expires, "use": USE, "ver": _password_version(user)},
        settings.jwt_secret, algorithm=ALGORITHM,
    )
    return f"{settings.public_url.rstrip('/')}/set-password?token={token}"


def user_for_password_token(token: str, db: Session) -> User:
    invalid = BadRequest("الرابط غير صالح أو انتهت مدته. اطلب رابطًا جديدًا.")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise invalid
    if payload.get("use") != USE or not str(payload.get("sub", "")).isdigit():
        raise invalid
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or payload.get("ver") != _password_version(user):
        raise invalid
    return user
