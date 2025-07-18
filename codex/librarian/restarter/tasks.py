"""Codex Restarter Taskss."""

from abc import ABC


class CodexRestarterTask(ABC):  # noqa: B024
    """Restart and Shutdown."""


class CodexRestartTask(CodexRestarterTask):
    """Restart Codex."""


class CodexShutdownTask(CodexRestarterTask):
    """Shutdown Codex."""
