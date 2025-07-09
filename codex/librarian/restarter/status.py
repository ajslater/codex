"""Restarter Statii."""

from abc import ABC

from codex.librarian.status import Status


class CodexRestarterStatus(Status, ABC):
    """Codex Restarter Statii."""


class CodexRestarterRestartStatus(CodexRestarterStatus):
    """Codex Restarter Restart Status."""

    CODE = "RCR"
    VERB = "Restart"
    _verbed = "Restarted"
    ITEM_NAME = "Codex server"
    SINGLE = True


class CodexRestarterStopStatus(CodexRestarterStatus):
    """Codex Restarter Restart Status."""

    CODE = "RCS"
    VERB = "Stop"
    _verbed = "Stopped"
    ITEM_NAME = "Codex server"
    SINGLE = True


RESTARTER_STATII = (CodexRestarterRestartStatus, CodexRestarterStopStatus)
