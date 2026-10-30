"""The errors a service raises, and the HTTP status each becomes.

A service says what went wrong, not how to answer it: it raises one of these instead of
FastAPI's `HTTPException`. One handler in `main.py` turns them into the same status and body
the routes answered before, so the frontend reads them unchanged, and a job can call the very
same service a page does without FastAPI anywhere in sight.
"""


class DomainError(Exception):
    """Something the portal refuses to do, with the Arabic sentence the user sees."""

    status_code = 400

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message

    def body(self):
        """What goes under "detail" in the answer."""
        return self.message


class BadRequest(DomainError):
    """What was sent cannot be used at all, e.g. a password link that is not a valid token: 400.

    Apart from `Invalid`, which is about a value failing a rule and carries a message per field.
    """

    status_code = 400


class NotFound(DomainError):
    """Asked for something that is not there: 404."""

    status_code = 404


class Unauthorized(DomainError):
    """Not signed in, or the credentials given are not right: 401."""

    status_code = 401


class TooManyRequests(DomainError):
    """Asked too often, e.g. one account's failed logins: 429."""

    status_code = 429


class Unavailable(DomainError):
    """The portal cannot do this just now and it is worth trying again: 503."""

    status_code = 503


class Conflict(DomainError):
    """Refused because of the state of things, e.g. a name already taken: 409."""

    status_code = 409


class Forbidden(DomainError):
    """The user may not do this: 403."""

    status_code = 403


class Invalid(DomainError):
    """What was sent does not pass the rules: 422.

    `fields` carries a message per field, which is how a form's errors reach the screen:
    the answer is then `{"detail": {"errors": {"<field>": "<message>"}}}`, as today.
    """

    status_code = 422

    def __init__(self, message: str = "", fields: dict[str, str] | None = None):
        super().__init__(message)
        self.fields = fields or {}

    def body(self):
        return {"errors": self.fields} if self.fields else self.message


class SyncError(DomainError):
    """Why the Daftra documents an approved request needs could not be created, in words the
    manager can act on.

    It lives here rather than in `invoicing` because `clients` raises it too — the client is one
    of the things approving creates — and neither module may import the other.
    """

    def __init__(self, message: str, from_daftra: bool = False):
        super().__init__(message)
        # Whether Daftra itself refused or failed, rather than one of our own checks
        self.from_daftra = from_daftra

    @property
    def status_code(self) -> int:
        return 502 if self.from_daftra else 409


class ExternalFailure(DomainError):
    """Someone we depend on (Daftra, the mail server) failed us: 502."""

    status_code = 502
