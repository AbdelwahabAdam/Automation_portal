"""Two-step login: after the password, a 6-digit code sent to the user's email."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from .config import settings
from .models import User
from .text import digits

CODE_MINUTES = 10
# Wrong tries allowed on one code before a new one has to be sent
MAX_ATTEMPTS = 5
RESEND_SECONDS = 60


def applies(user: User) -> bool:
    """Always for admins, and for any user who turned it on."""
    return bool(user.mfa_enabled or (settings.require_admin_mfa and user.is_admin))


def _hash(user: User, code: str) -> str:
    return hashlib.sha256(f"{user.id}:{code}:{settings.jwt_secret}".encode()).hexdigest()


def seconds_until_resend(user: User) -> int:
    """How long before another code may be sent; 0 when one can go now."""
    # No wait once the last code has been used, or the user would be asked for a code they cannot get
    if user.mfa_code_sent_at is None or not user.mfa_code_hash:
        return 0
    waited = (datetime.now(timezone.utc) - user.mfa_code_sent_at).total_seconds()
    return max(0, int(RESEND_SECONDS - waited))


def new_code(user: User) -> str:
    """Replaces any earlier code. Only its hash is stored."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(timezone.utc)
    user.mfa_code_hash = _hash(user, code)
    user.mfa_code_expires = now + timedelta(minutes=CODE_MINUTES)
    user.mfa_code_sent_at = now
    user.mfa_code_attempts = 0
    return code


def clear_code(user: User):
    user.mfa_code_hash = None
    user.mfa_code_expires = None
    user.mfa_code_attempts = 0


def check_code(user: User, code: str) -> bool:
    """True once for the right code. Counts wrong tries, so the caller must commit either way."""
    typed = digits(code)
    if (not user.mfa_code_hash or user.mfa_code_expires is None
            or user.mfa_code_expires < datetime.now(timezone.utc) or user.mfa_code_attempts >= MAX_ATTEMPTS):
        return False
    user.mfa_code_attempts += 1
    if not hmac.compare_digest(user.mfa_code_hash, _hash(user, typed)):
        return False
    clear_code(user)
    return True


def mask_email(email: str) -> str:
    """h•••@gmail.com: enough to recognise the inbox without showing the address."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}•••@{domain}"
