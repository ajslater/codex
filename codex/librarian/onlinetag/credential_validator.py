"""
Validate online-source credentials with comicbox's own probe.

Used by the admin tagging settings page to give operators an immediate
yes/no on whether a saved (or in-the-form) credential set actually
works against Metron / Comic Vine — so they don't discover problems
only when a real tagging run fails halfway through.

Each source's ``probe()`` is its cheapest authenticated request, sent
once on a private client with no response cache and never retried, so
the verdict is the server's rather than a cached or pooled answer.
Metron's goes through comicbox's process-wide rate gate; Comic Vine's
is counted against the real shared rate-limit bucket under codex's
comicbox cache dir — the one tagging runs draw on — and is refused
outright when that pool is already spent.

A successful Metron check also reports the account's live rate limits,
which the probe reads off the ``X-RateLimit-*`` headers of its own
response. The daily "sustained" limit varies by Metron OpenCollective
donor tier (5,000-25,000/day), so it is only discoverable this way.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from comicbox.formats.base.online.retry import RetryCategory

from codex.librarian.onlinetag.sources import (
    SOURCES,
    SUPPORTED_SOURCES,
    source_credentials,
)
from codex.settings import COMICBOX_ONLINE_CONFIG

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from comicbox.formats.base.online.sources.base import OnlineSource
    from comicbox.online_session import OnlineCredentials

    from codex.librarian.onlinetag.sources import OnlineTagSource

# The sources codex registered, not every name comicbox knows: a source
# comicbox adds stays unknown here until codex can drive it.
KNOWN_SOURCES: Final[frozenset[str]] = frozenset(SUPPORTED_SOURCES)

#: What a probe returns: ``{window: {"limit", "remaining", "reset_epoch"}}``.
type _Windows = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class RateLimitWindowInfo:
    """One rate-limit window (burst or sustained) as limit/remaining counts."""

    limit: int | None = None
    remaining: int | None = None


@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    """
    A source account's live rate limits, mirrored from the probe's windows.

    ``reset_epoch`` values are deliberately dropped: the burst window
    resets within a minute (stale before an admin reads it) and the
    sustained reset isn't worth datetime plumbing for a one-shot
    validation chip.
    """

    burst: RateLimitWindowInfo = RateLimitWindowInfo()
    sustained: RateLimitWindowInfo = RateLimitWindowInfo()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating one source's credentials."""

    ok: bool
    error: str | None = None
    rate_limits: RateLimitInfo | None = None


def _window_info(window: Mapping[str, Any] | None) -> RateLimitWindowInfo:
    if not window:
        return RateLimitWindowInfo()
    return RateLimitWindowInfo(
        limit=window.get("limit"), remaining=window.get("remaining")
    )


def _rate_limits(spec: OnlineTagSource, windows: _Windows) -> RateLimitInfo | None:
    """Codex-shaped rate limits, or None when the probe reported none it shows."""
    info = RateLimitInfo(
        **{
            field: _window_info(windows.get(window))
            for field, window in spec.rate_limit_windows.items()
        }
    )
    return None if info == RateLimitInfo() else info


# Shown when the client's exception carries no message of its own.
_FALLBACK_ERRORS: Final[Mapping[RetryCategory | None, str]] = MappingProxyType(
    {
        RetryCategory.AUTH: "Authentication failed.",
        RetryCategory.RATE_LIMIT: "Rate limited.",
    }
)


def _error_message(source: OnlineSource, exc: Exception) -> str:
    """Name what went wrong: the exception's first line, else its category."""
    # simyan raises ``RateLimitError(None)`` for a 429 with no error body,
    # and str() of that is the word "None". Some upstream errors carry a
    # whole HTML page, of which only the first line is the message.
    text = str(exc) if exc.args and exc.args[0] is not None else ""
    first_line = text.partition("\n")[0].strip()
    category = source.classify_retry_exception(exc)
    return first_line or _FALLBACK_ERRORS.get(category, type(exc).__name__)


def _validate(spec: OnlineTagSource, creds: OnlineCredentials) -> ValidationResult:
    source = spec.source_class()(
        source_credentials(spec.name, creds), COMICBOX_ONLINE_CONFIG.online
    )
    if not source.is_configured():
        return ValidationResult(ok=False, error="API key required.")
    try:
        windows = source.probe()
    except Exception as exc:
        return ValidationResult(ok=False, error=_error_message(source, exc))
    return ValidationResult(ok=True, rate_limits=_rate_limits(spec, windows or {}))


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
    return {name: _validate(SOURCES[name], creds) for name in sorted(targets)}
