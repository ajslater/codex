"""Codex Restarter Taskss."""

from codex.librarian.tasks import LibrarianTask


class CodexRestarterTask(LibrarianTask):
    """Restart and Shutdown."""


class CodexRestartTask(CodexRestarterTask):
    """Restart Codex."""


class CodexShutdownTask(CodexRestarterTask):
    """Shutdown Codex."""
