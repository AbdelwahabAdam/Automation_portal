import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user: User) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user.id), "exp": expires}, settings.jwt_secret, algorithm=ALGORITHM)


def _password_version(user: User) -> str:
    """Changes whenever the password does, which is what makes a password link single-use."""
    return hashlib.sha256(f"{user.id}:{user.password_hash or ''}".encode()).hexdigest()[:16]


def create_password_link(user: User) -> str:
    """A link the user opens to set their password, for an invitation or a reset."""
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.password_link_hours)
    token = jwt.encode(
        {"sub": str(user.id), "exp": expires, "use": "set_password", "ver": _password_version(user)},
        settings.jwt_secret, algorithm=ALGORITHM,
    )
    return f"{settings.public_url.rstrip('/')}/set-password?token={token}"


def user_for_password_token(token: str, db: Session) -> User:
    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "الرابط غير صالح أو انتهت مدته. اطلب رابطًا جديدًا.")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise invalid
    if payload.get("use") != "set_password":
        raise invalid
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or payload.get("ver") != _password_version(user):
        raise invalid
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise unauthorized
    # A password link is not a login
    if "use" in payload:
        raise unauthorized
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_page(*page_keys: str):
    """Allows users who can open at least one of the given pages."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not set(page_keys) & set(user.pages):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ليست لديك صلاحية لهذه الصفحة")
        return user

    return dependency


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "هذه الصفحة لمدير النظام فقط")
    return user
