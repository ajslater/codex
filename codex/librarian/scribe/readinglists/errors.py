"""
Cache-backed reading-list fetch and import errors, for the admin screen.

Fetches run on the online-tagging thread and writes on the scribe, so a
failure never reaches the request that queued it. These accessors keep the
failures where the admin Reading Lists tab can show and clear them, in the
``tagging`` cache, which survives a restart and the broad clears of the
default cache.
"""

from typing import Any, Final

from django.utils import timezone

from codex.cache import tagging_cache as cache

_ERRORS_KEY: Final = "readinglists:errors"
# Newest win: a whole catalog that fails cannot grow the blob without bound.
_MAX_ERRORS: Final = 100


def add_reading_list_error(kind: str, ref: str, error: str) -> None:
    """Record one failed fetch or import."""
    errors = list(cache.get(_ERRORS_KEY) or [])
    errors.append(
        {
            "kind": kind,
            "ref": ref,
            "error": error,
            "created_at": timezone.now().isoformat(),
        }
    )
    cache.set(_ERRORS_KEY, errors[-_MAX_ERRORS:], None)


def get_reading_list_errors() -> list[dict[str, Any]]:
    """Return the recorded errors, oldest first."""
    return list(cache.get(_ERRORS_KEY) or [])


def clear_reading_list_errors() -> None:
    """Forget every recorded error."""
    cache.delete(_ERRORS_KEY)
