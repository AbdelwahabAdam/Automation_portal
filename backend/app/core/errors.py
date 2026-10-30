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


class NotFound(DomainError):
    """Asked for something that is not there: 404."""

    status_code = 404


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


class ExternalFailure(DomainError):
    """Someone we depend on (Daftra, the mail server) failed us: 502."""

    status_code = 502
