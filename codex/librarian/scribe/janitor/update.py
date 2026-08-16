"""Codex auto update."""

import subprocess
import sys
from importlib import invalidate_caches
from importlib.util import find_spec
from shutil import which
from typing import Final

from codex.librarian.restarter.tasks import CodexRestartTask
from codex.librarian.scribe.janitor.cleanup import JanitorCleanup
from codex.librarian.scribe.janitor.status import JanitorCodexUpdateStatus
from codex.models.admin import Timestamp
from codex.util import is_docker
from codex.version import PACKAGE_NAME, VERSION, get_version, is_outdated

# Long enough for a slow index and a source build, short enough that a
# hung installer doesn't wedge the scribe thread forever. Every import,
# search index sync and janitor job waits behind this one queue.
_INSTALL_TIMEOUT: Final = 600
_STDERR_TAIL: Final = 20


class JanitorCodexUpdate(JanitorCleanup):
    """Auto Update codex methods for janitor."""

    def _is_outdated(self) -> bool:
        """Is codex outdated."""
        ts = Timestamp.objects.get(key=Timestamp.Choices.CODEX_VERSION.value)
        latest_version = ts.value
        result = is_outdated(VERSION, latest_version)
        self.log.debug(f"{latest_version=} > {VERSION=} = {result}")
        return result

    def _installer_args(self) -> tuple[str, ...] | None:
        """
        Build the upgrade command for however this codex was installed.

        pip is the common case but it isn't guaranteed to exist: uv and
        pipx environments omit it, and the Codex docker image uninstalls
        it from the runtime layer. uv installs into an explicit
        interpreter, so point it at this one rather than whatever it
        would discover on its own.
        """
        if find_spec("pip"):
            return (sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME)
        if uv := which("uv"):
            return (
                uv,
                "pip",
                "install",
                "--upgrade",
                "--python",
                sys.executable,
                PACKAGE_NAME,
            )
        reason = (
            f"Cannot update Codex: neither pip nor uv is available to {sys.executable}."
        )
        if is_docker():
            reason += " Codex is running in Docker. Pull a new image to update."
        self.log.error(reason)
        return None

    def _run_installer(self, args: tuple[str, ...]) -> bool:
        """Run the installer, logging its output on failure."""
        self.log.info(f"Updating Codex with: {' '.join(args)}")
        try:
            subprocess.run(  # noqa: S603
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=_INSTALL_TIMEOUT,
            )
        except subprocess.CalledProcessError as exc:
            # The installer's own diagnosis is worth far more to an
            # admin than a traceback out of subprocess.
            output = (exc.stderr or exc.stdout or "").strip().splitlines()
            tail = "\n".join(output[-_STDERR_TAIL:])
            reason = f"Codex update failed with code {exc.returncode}:\n{tail}"
        except subprocess.TimeoutExpired:
            reason = (
                f"Codex update timed out after {_INSTALL_TIMEOUT} seconds: {args[0]}"
            )
        else:
            return True
        self.log.error(reason)
        return False

    def _update_codex(self, *, force: bool) -> bool:
        """
        Install the latest codex if warranted. Return whether it ran.

        The Auto Update admin flag is *not* checked here. It gates the
        nightly path only, at the point where the version check chains
        into this task. An admin who pushes the Update Codex button in
        the jobs tab is asking for an update, flag or no flag.
        """
        if force:
            self.log.info("Forcing update of Codex.")
        elif self._is_outdated():
            self.log.info("Codex seems outdated. Trying to update.")
        else:
            self.log.info("Codex is up to date.")
            return False

        args = self._installer_args()
        if not args:
            return False
        return self._run_installer(args)

    def update_codex(self, *, force: bool) -> None:
        """Update the package and restart everything if the version changed."""
        status = JanitorCodexUpdateStatus()
        try:
            self.status_controller.start(status)
            installed = self._update_codex(force=force)
        except Exception:
            self.log.exception("Updating Codex software")
            installed = False
        finally:
            self.status_controller.finish(status)

        if not installed:
            return

        # Restart if changed version. importlib.metadata caches its
        # distribution search per directory mtime, so drop the caches
        # before reading the version the installer just wrote. A stale
        # read here means a successful update never restarts into the
        # new code.
        invalidate_caches()
        new_version = get_version()
        if new_version != VERSION:
            self.log.success(f"Codex was updated from {VERSION} to {new_version}.")
            self.librarian_queue.put(CodexRestartTask())
        else:
            reason = (
                "Codex updated to the same version that was previously"
                f" installed: {VERSION}."
            )
            self.log.info(reason)
