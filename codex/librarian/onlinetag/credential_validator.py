"""
Validate online-source credentials by making a tiny authenticated call.

Used by the admin tagging settings page to give operators an immediate
yes/no on whether a saved (or in-the-form) credential set actually
works against Metron / Comic Vine — so they don't discover problems
only when a real tagging run fails halfway through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

    from comicbox.online_session import OnlineCredentials

KNOWN_SOURCES: frozenset[str] = frozenset({"metron", "comicvine"})

_COMICVINE_TIMEOUT_SECS: float = 10.0


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating one source's credentials."""

    ok: bool
    error: str | None = None


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
    return ValidationResult(ok=True)


def _validate_comicvine(creds: OnlineCredentials) -> ValidationResult:
    if not creds.comicvine_key:
        return ValidationResult(ok=False, error="API key required.")
    from simyan.comicvine import Comicvine
    from simyan.errors import AuthenticationError, ServiceError

    if creds.comicvine_url:
        cv = Comicvine(
            api_key=creds.comicvine_key,
            cache=None,
            base_url=creds.comicvine_url,
            user_agent="codex-credential-check",
            timeout=_COMICVINE_TIMEOUT_SECS,
        )
    else:
        cv = Comicvine(
            api_key=creds.comicvine_key,
            cache=None,
            user_agent="codex-credential-check",
            timeout=_COMICVINE_TIMEOUT_SECS,
        )
    try:
        cv.list_publishers(params={"limit": "1"}, max_results=1)
    except AuthenticationError as err:
        return ValidationResult(ok=False, error=str(err) or "Authentication failed.")
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
