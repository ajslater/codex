"""Update the codex python package."""

import os
import signal
import subprocess
import sys

from versio.version import Version

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.tasks import LibrarianShutdownTask
from codex.models import AdminFlag
from codex.models.admin import Timestamp
from codex.status import Status
from codex.version import VERSION, get_version
from codex.worker_base import WorkerBaseMixin


class UpdateMixin(WorkerBaseMixin):
    """Update codex methods for janitor."""

    def _is_outdated(self):
        """Is codex outdated."""
        result = False
        ts = Timestamp.objects.get(key=Timestamp.TimestampChoices.CODEX_VERSION.value)
        latest_version = ts.version
        versio_latest_version = Version(latest_version)

        installed_versio_version = Version(VERSION)
        if versio_latest_version.parts[1] and not installed_versio_version.parts[1]:  # type: ignore
            pre_blurb = "latest version is a prerelease. But installed version is not."
        else:
            result = versio_latest_version > installed_versio_version
            pre_blurb = ""
        self.log.debug(f"{latest_version=} > {VERSION=} = {result}{pre_blurb}")
        return result

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
                if not eau.on or not self._is_outdated():
                    self.log.info("Codex is up to date.")
                    return

                self.log.info("Codex seems outdated. Trying to update.")

            args = (
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "codex",
            )
            subprocess.run(  # noqa: S603
                args,
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
