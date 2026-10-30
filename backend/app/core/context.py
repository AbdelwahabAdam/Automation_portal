"""Who is acting, and from where.

Services take an `Actor` instead of FastAPI's request, so the same service can be called by a
route, by a job and by a test. The activity log reads the address and the browser from here.
"""

from dataclasses import dataclass, replace
from typing import Any

# How a job names itself in the activity log when no person asked for the work
SYSTEM_LABEL = "المزامنة الليلية"


@dataclass(frozen=True)
class Actor:
    """The signed-in user and the call they made it from; `user` is None for a job."""

    user: Any = None
    ip: str = ""
    user_agent: str = ""
    # What the activity log writes when there is no user, e.g. a failed login or a nightly job
    username: str = ""

    @property
    def name(self) -> str:
        return self.user.username if self.user is not None else self.username

    @classmethod
    def of(cls, user: Any, http_request: Any = None) -> "Actor":
        """A user, with the address and browser of the call if there is one."""
        client = getattr(http_request, "client", None)
        headers = getattr(http_request, "headers", None)
        return cls(
            user=user,
            ip=client.host if client else "",
            user_agent=((headers.get("user-agent") if headers else "") or "")[:300],
            username=getattr(user, "username", "") or "",
        )

    def replace_user(self, user: Any) -> "Actor":
        """The same caller, now known to be this user — e.g. once a login has identified them."""
        return replace(self, user=user, username=getattr(user, "username", "") or self.username)

    @classmethod
    def system(cls, label: str = SYSTEM_LABEL) -> "Actor":
        """A job acting on nobody's behalf."""
        return cls(user=None, username=label)
