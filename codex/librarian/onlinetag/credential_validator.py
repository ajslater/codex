"""
Validate online-source credentials by making a tiny authenticated call.

Used by the admin tagging settings page to give operators an immediate
yes/no on whether a saved (or in-the-form) credential set actually
works against Metron / Comic Vine — so they don't discover problems
only when a real tagging run fails halfway through.

A successful Metron check also reports the account's live rate limits,
which mokkari 4 reads off the ``X-RateLimit-*`` headers of the
validation response itself. The daily "sustained" limit varies by
Metron OpenCollective donor tier (5,000-25,000/day), so it is only
discoverable this way.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

from comicbox.formats.base.online import SOURCE_NAMES

if TYPE_CHECKING:
    from collections.abc import Collection

    from comicbox.online_session import OnlineCredentials
    from mokkari.session import RateLimitStatus

# comicbox owns the canonical online-tag source names (metron, comicvine); derive
# from it so codex tracks a new source instead of hand-syncing a literal.
KNOWN_SOURCES: frozenset[str] = frozenset(SOURCE_NAMES)

_COMICVINE_TIMEOUT_SECS: float = 10.0


@dataclass(frozen=True, slots=True)
class RateLimitWindowInfo:
    """One rate-limit window (burst or sustained) as limit/remaining counts."""

    limit: int | None = None
    remaining: int | None = None


@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    """
    A source account's live rate limits, mirrored from mokkari's status.

    ``reset`` datetimes are deliberately dropped: the burst window resets
    within a minute (stale before an admin reads it) and the sustained
    reset isn't worth datetime plumbing for a one-shot validation chip.
    """

    burst: RateLimitWindowInfo = RateLimitWindowInfo()
    sustained: RateLimitWindowInfo = RateLimitWindowInfo()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating one source's credentials."""

    ok: bool
    error: str | None = None
    rate_limits: RateLimitInfo | None = None


def _extract_rate_limits(status: RateLimitStatus) -> RateLimitInfo | None:
    """Codex-shaped rate limits, or None when the source reported nothing."""
    burst = status.burst
    sustained = status.sustained
    if (
        burst.limit is None
        and burst.remaining is None
        and sustained.limit is None
        and sustained.remaining is None
    ):
        return None
    return RateLimitInfo(
        burst=RateLimitWindowInfo(limit=burst.limit, remaining=burst.remaining),
        sustained=RateLimitWindowInfo(
            limit=sustained.limit, remaining=sustained.remaining
        ),
    )


def _validate_metron(creds: OnlineCredentials) -> ValidationResult:
    if not (creds.metron_user and creds.metron_password):
        return ValidationResult(ok=False, error="Username and password required.")
    from mokkari.exceptions import ApiError, AuthenticationError
    from mokkari.session import Session

    session = Session(
        username=creds.metron_user,
        passwd=creds.metron_password,
        cache=None,
        user_agent="codex-credential-check",
    )
    try:
        session.publishers_list({"page": 1})
    except AuthenticationError as err:
        return ValidationResult(ok=False, error=str(err) or "Authentication failed.")
    except ApiError as err:
        return ValidationResult(ok=False, error=str(err) or "API error.")
    # The successful response carried the account's X-RateLimit-* headers.
    return ValidationResult(
        ok=True, rate_limits=_extract_rate_limits(session.rate_limit_status)
    )


def _validate_comicvine(creds: OnlineCredentials) -> ValidationResult:
    if not creds.comicvine_key:
        return ValidationResult(ok=False, error="API key required.")
    from requests_cache import DO_NOT_CACHE
    from simyan.comicvine import Comicvine
    from simyan.errors import AuthenticationError, ServiceError

    # simyan 3.x replaced the cache= kwarg with sqlite cache/ratelimit
    # files. A credential check must always hit the network — api_key is
    # excluded from simyan's cache key, so a cached response would
    # validate any key — so responses are never cached (DO_NOT_CACHE)
    # and both sqlite files land in a throwaway dir.
    with TemporaryDirectory(prefix="codex-credential-check-") as tmp:
        tmp_path = Path(tmp)
        # dict[str, Any] expansion because DO_NOT_CACHE is an int sentinel
        # that simyan's timedelta-typed cache_expiry accepts at runtime.
        kwargs: dict[str, Any] = {
            "api_key": creds.comicvine_key,
            "user_agent": "codex-credential-check",
            "timeout": _COMICVINE_TIMEOUT_SECS,
            "cache_path": tmp_path / "cache.sqlite",
            "cache_expiry": DO_NOT_CACHE,
            "ratelimit_path": tmp_path / "ratelimits.sqlite",
        }
        if creds.comicvine_url:
            kwargs["base_url"] = creds.comicvine_url
        cv = Comicvine(**kwargs)
        try:
            cv.list_publishers(params={"limit": "1"}, max_results=1)
        except AuthenticationError as err:
            return ValidationResult(
                ok=False, error=str(err) or "Authentication failed."
            )
        except ServiceError as err:
            return ValidationResult(ok=False, error=str(err) or "Service error.")
    return ValidationResult(ok=True)


_VALIDATORS = {
    "metron": _validate_metron,
    "comicvine": _validate_comicvine,
}


def validate_credentials(
    creds: OnlineCredentials, sources: Collection[str] | None = None
) -> dict[str, ValidationResult]:
    """
    Validate credentials for each requested source.

    ``sources`` defaults to every source codex knows about. Unknown
    source names are silently skipped — the caller has already
    constrained the inputs.
    """
    targets = KNOWN_SOURCES if sources is None else (set(sources) & KNOWN_SOURCES)
    return {name: _VALIDATORS[name](creds) for name in sorted(targets)}
