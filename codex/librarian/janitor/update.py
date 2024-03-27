"""Update the codex python package."""

import os
import signal
import subprocess
import sys

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.tasks import LibrarianShutdownTask
from codex.models import AdminFlag
from codex.status import Status
from codex.version import PACKAGE_NAME, VERSION, get_version, is_outdated
from codex.worker_base import WorkerBaseMixin


class UpdateMixin(WorkerBaseMixin):
    """Update codex methods for janitor."""

    def update_codex(self, force=False):
        """Update the package and restart everything if the version changed."""
        status = Status(JanitorStatusTypes.CODEX_UPDATE)
        try:
            self.status_controller.start(status)
            if force:
                self.log.info("Forcing update of Codex.")
            else:
                eau = AdminFlag.objects.only("on").get(
                    key=AdminFlag.FlagChoices.AUTO_UPDATE.value
                )
                if not eau.on or not is_outdated(PACKAGE_NAME):
                    self.log.info("Codex is up to date.")
                    return

                self.log.info("Codex seems outdated. Trying to update.")

            subprocess.run(
                (  # noqa: S603
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "codex",
                ),
                check=True,
            )
        except Exception:
            self.log.exception("Updating Codex software")
        finally:
            self.status_controller.finish(status)

        # Restart if changed version.
        new_version = get_version()
        restart = new_version != VERSION

        if restart:
            self.log.info(f"Codex was updated from {VERSION} to {new_version}.")
            self.restart_codex()
        else:
            self.log.warning(
                "Codex updated to the same version that was previously"
                f" installed: {VERSION}."
            )

    def _shutdown_codex(self, status, name, sig):
        """Send a system signal as handled in run.py."""
        status = Status(status)
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
        self._shutdown_codex(JanitorStatusTypes.CODEX_STOP, "stop", signal.SIGTERM)

    def restart_codex(self):
        """Restart codex."""
        self._shutdown_codex(
            JanitorStatusTypes.CODEX_RESTART, "restart", signal.SIGUSR1
        )
