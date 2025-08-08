"""Codex auto update."""

import subprocess
import sys

from versio.version import Version

from codex.choices.admin import AdminFlagChoices
from codex.librarian.restarter.tasks import CodexRestartTask
from codex.librarian.scribe.janitor.cleanup import JanitorCleanup
from codex.librarian.scribe.janitor.status import JanitorCodexUpdateStatus
from codex.models import AdminFlag
from codex.models.admin import Timestamp
from codex.version import VERSION, get_version


class JanitorCodexUpdate(JanitorCleanup):
    """Auto Update codex methods for janitor."""

    def _is_outdated(self):
        """Is codex outdated."""
        result = False
        if not VERSION:
            self.log.warning("Cannot determine installed Codex version.")
            return result
        ts = Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value)
        latest_version = ts.version
        versio_latest_version = Version(latest_version)

        installed_versio_version = Version(VERSION)
        if versio_latest_version.parts[1] and not installed_versio_version.parts[1]:  # pyright: ignore[reportIndexIssue]
            pre_blurb = "latest version is a prerelease. But installed version is not."
        else:
            result = versio_latest_version > installed_versio_version
            pre_blurb = ""
        self.log.debug(f"{latest_version=} > {VERSION=} = {result}{pre_blurb}")
        return result

    def _update_codex(self, *, force: bool):
        if force:
            self.log.info("Forcing update of Codex.")
        else:
            eau = AdminFlag.objects.only("on").get(
                key=AdminFlagChoices.AUTO_UPDATE.value
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

    def update_codex(self, *, force: bool):
        """Update the package and restart everything if the version changed."""
        status = JanitorCodexUpdateStatus()
        try:
            self.status_controller.start(status)
            self._update_codex(force=force)
        except Exception:
            self.log.exception("Updating Codex software")
        finally:
            self.status_controller.finish(status)

        # Restart if changed version.
        new_version = get_version()
        restart = new_version != VERSION

        if restart:
            self.log.success(f"Codex was updated from {VERSION} to {new_version}.")
            self.librarian_queue.put(CodexRestartTask())
        else:
            reason = (
                "Codex updated to the same version that was previously"
                f" installed: {VERSION}."
            )
            self.log.info(reason)
