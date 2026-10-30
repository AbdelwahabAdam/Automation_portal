"""Who is calling: the login token, password hashing, and the permission a route needs.

`core` knows nothing above it, so it cannot import the user model. Instead `identity` registers
a loader at import (`set_user_loader`), and this file asks that for the user a token names. So
every module can say `require("…")` without importing identity, and identity can still write to
the activity log.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi import Request as HttpRequest
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import permissions
from .config import settings
from .context import Actor
from .database import get_db

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)

# Set by identity at import: (db, user_id) -> the user, or None if there is none or it is inactive
_load_user: Callable[[Session, int], Any] | None = None


def set_user_loader(loader: Callable[[Session, int], Any]):
    """identity says how to fetch the user a token names."""
    global _load_user
    _load_user = loader


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user.id), "exp": expires}, settings.jwt_secret, algorithm=ALGORITHM)


def decode(token: str) -> dict:
    """The token's payload, or jwt's own error."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        payload = decode(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized
    # A password link is not a login
    if "use" in payload or not str(payload.get("sub", "")).isdigit():
        raise unauthorized
    if _load_user is None:                       # identity was never imported: nothing can be signed in
        raise unauthorized
    user = _load_user(db, int(payload["sub"]))
    if user is None:
        raise unauthorized
    return user


def caller(http_request: HttpRequest) -> Actor:
    """The Actor behind a call nobody has signed in for yet, e.g. a login attempt."""
    return Actor.of(None, http_request)


def acting(user_dependency):
    """A dependency giving the Actor behind the call: the user this route needs, and where from.

    Routers pass this into the services instead of FastAPI's request, so a job can call the very
    same service with `Actor.system()`.
    """

    def dependency(http_request: HttpRequest, user=Depends(user_dependency)) -> Actor:
        return Actor.of(user, http_request)

    return dependency


NO_ACCESS = "ليست لديك صلاحية لهذه الصفحة"


def require(*keys: str):
    """Allows users holding at least one of these permissions. An admin holds every one.

    The server checks every call this way: opening a form, creating, saving, submitting,
    uploading, viewing, deciding. Hiding a button is never the check.
    """

    def dependency(user=Depends(get_current_user)):
        if not permissions.holds(user, *keys):
            raise HTTPException(status.HTTP_403_FORBIDDEN, NO_ACCESS)
        return user

    return dependency


def require_any_form(*does: str):
    """Allows users who may do that with at least one form — what the lookups the forms use need,
    and what opening النماذج or المراجعة needs."""

    def dependency(user=Depends(get_current_user)):
        if not any(permissions.holds_any_form(user, one) for one in does):
            raise HTTPException(status.HTTP_403_FORBIDDEN, NO_ACCESS)
        return user

    return dependency


# Anyone with a permission on any form: the client search, the products, Daftra's lists
form_user = require_any_form(permissions.SUBMIT, permissions.VIEW, permissions.REVIEW)


def require_admin(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "هذه الصفحة لمدير النظام فقط")
    return user
