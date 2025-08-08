"""Update the codex python package."""

import os
import signal

from codex.librarian.restarter.status import (
    CodexRestarterRestartStatus,
    CodexRestarterStatus,
    CodexRestarterStopStatus,
)
from codex.librarian.restarter.tasks import (
    CodexRestartTask,
    CodexShutdownTask,
)
from codex.librarian.tasks import LibrarianShutdownTask
from codex.librarian.worker import WorkerStatusBase


class CodexRestarter(WorkerStatusBase):
    """Codex restarter."""

    def _shutdown_codex(
        self, status: CodexRestarterStatus, name: str, sig: signal.Signals
    ):
        """Send a system signal as handled in run.py."""
        try:
            self.status_controller.start(status)
            self.log.info(f"Sending {name} signal.")
            main_pid = os.getppid()
            os.kill(main_pid, sig)
        finally:
            self.status_controller.finish(status)
            # Librarian shutdown must come after the kill signal.
            self.librarian_queue.put(LibrarianShutdownTask())

    def shutdown_codex(self):
        """Shutdown codex."""
        self._shutdown_codex(CodexRestarterStopStatus(), "stop", signal.SIGTERM)

    def restart_codex(self):
        """Restart codex."""
        self._shutdown_codex(CodexRestarterRestartStatus(), "restart", signal.SIGUSR1)

    def handle_task(self, task):
        """Handle Codex reatarter tasks."""
        match task:
            case CodexRestartTask():
                self.restart_codex()
            case CodexShutdownTask():
                self.shutdown_codex()
            case _:
                self.log.warning(f"Unknown Codex RestarterTask: f{task}")
