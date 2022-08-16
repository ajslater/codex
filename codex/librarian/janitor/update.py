"""Update the codex python package."""
import os
import signal
import subprocess  # nosec
import sys

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.status_control import StatusControl
from codex.models import AdminFlag
from codex.settings.logging import get_logger
from codex.version import PACKAGE_NAME, VERSION, get_version, is_outdated


LOG = get_logger(__name__)


def update_codex(force=False):
    """Update the package and restart everything if the version changed."""
    try:
        StatusControl.start(JanitorStatusTypes.CODEX_UPDATE)
        if force:
            LOG.info("Forcing update of Codex.")
        else:
            eau = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_AUTO_UPDATE)
            if not eau.on or not is_outdated(PACKAGE_NAME):
                LOG.verbose("Codex is up to date.")
                return

            LOG.info("Codex seems outdated. Trying to update.")

        subprocess.run(  # nosec
            (sys.executable, "-m", "pip", "install", "--upgrade", "codex"), check=True
        )
    except Exception as exc:
        LOG.error(exc)
    finally:
        StatusControl.finish(JanitorStatusTypes.CODEX_UPDATE)

    # Restart if changed version.
    new_version = get_version()
    restart = VERSION != new_version

    if restart:
        LOG.info(f"Codex was updated from {VERSION} to {new_version}.")
        restart_codex()
    else:
        LOG.warning(
            "Codex updated to the same version that was previously"
            f" installed: {VERSION}."
        )


def restart_codex():
    """Send a system SIGUSR1 signal as handled in run.py."""
    try:
        StatusControl.start(JanitorStatusTypes.CODEX_RESTART)
        LOG.info("Sending restart signal.")
        main_pid = os.getppid()
        os.kill(main_pid, signal.SIGUSR1)
    finally:
        StatusControl.finish(JanitorStatusTypes.CODEX_RESTART)
