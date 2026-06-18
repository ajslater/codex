"""
DB-aware DRF throttle classes.

Each subclass overrides :meth:`SimpleRateThrottle.get_rate` to consult
the :class:`ThrottleSettings` singleton first, falling back to the
DRF defaults (which themselves are sourced from TOML / env at boot
via ``DEFAULT_THROTTLE_RATES``). Admin edits via the Throttling tab
take effect on the next request — no restart needed.

A rate of ``None`` (returned when both DB value and settings value
are ``0``) makes DRF's :class:`SimpleRateThrottle` short-circuit to
``allow_request → True``: effectively disabling the limiter for that
scope.
"""

from typing import override

from rest_framework.throttling import (
    AnonRateThrottle as _AnonRateThrottle,
)
from rest_framework.throttling import (
    ScopedRateThrottle as _ScopedRateThrottle,
)
from rest_framework.throttling import (
    SimpleRateThrottle,
)
from rest_framework.throttling import (
    UserRateThrottle as _UserRateThrottle,
)

from codex.settings.db import get_throttle_rate_string


def _db_rate_for(throttle: SimpleRateThrottle) -> str | None:
    """Return the DB-configured rate string for the throttle's scope, or None."""
    scope = getattr(throttle, "scope", None)
    if not scope:
        return None
    return get_throttle_rate_string(scope)


class AnonRateThrottle(_AnonRateThrottle):
    """Anonymous-user rate throttle backed by ThrottleSettings."""

    @override
    def get_rate(self) -> str | None:
        """Prefer DB-configured rate; fall back to DRF settings."""
        return _db_rate_for(self) or super().get_rate()


class UserRateThrottle(_UserRateThrottle):
    """Authenticated-user rate throttle backed by ThrottleSettings."""

    @override
    def get_rate(self) -> str | None:
        """Prefer DB-configured rate; fall back to DRF settings."""
        return _db_rate_for(self) or super().get_rate()


class ScopedRateThrottle(_ScopedRateThrottle):
    """Scoped rate throttle backed by ThrottleSettings."""

    @override
    def get_rate(self) -> str | None:
        """Prefer DB-configured rate; fall back to DRF settings."""
        # ScopedRateThrottle reads ``scope`` from the view at request
        # time via ``allow_request``; before that runs the attribute is
        # unset and the DB lookup short-circuits to None.
        return _db_rate_for(self) or super().get_rate()
