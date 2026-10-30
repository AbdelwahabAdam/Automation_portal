"""The Daftra lists the portal keeps for a while, because they change rarely.

Daftra being briefly down must not empty a list the portal already has, so a loader that
fails falls back to what was cached before.
"""

import threading
import time

from .errors import DaftraError

CACHE_SECONDS = 15 * 60

_cache: dict[str, tuple[float, list]] = {}
# Re-entrant: a list's loader may use another cached list (e.g. categories with their locations)
_lock = threading.RLock()


def cached(key: str, loader, seconds: int = CACHE_SECONDS) -> list:
    with _lock:
        entry = _cache.get(key)
    if entry and time.monotonic() - entry[0] < seconds:
        return entry[1]
    # Loaded without holding the lock: a slow list (e.g. one reading every client) must not hold up the others
    try:
        value = loader()
    except DaftraError:
        # Daftra being down should not empty a list we already have
        if entry:
            return entry[1]
        raise
    with _lock:
        _cache[key] = (time.monotonic(), value)
    return value


def forget(key: str):
    """Drops a cached list, so the next ask reads Daftra again."""
    with _lock:
        _cache.pop(key, None)


def clear():
    with _lock:
        _cache.clear()
