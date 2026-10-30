"""What a Daftra call raises. Kept apart so the HTTP code, the fake and the cache all share them."""


class DaftraError(Exception):
    """Daftra refused the call, or could not be reached. The message is Daftra's own."""


class NotFound(DaftraError):
    """Daftra answered 404: the record is not there (any more)."""
