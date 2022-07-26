"""Update the codex python package."""
import os
import signal
import subprocess
import sys

from codex.librarian.status import librarian_status_done, librarian_status_update
from codex.models import AdminFlag
from codex.settings.logging import get_logger
from codex.version import PACKAGE_NAME, VERSION, get_version, is_outdated


UPDATE_CODEX_STATUS_KEYS = {"type": "Update Codex"}
RESTART_CODEX_STATUS_KEYS = {"type": "Restart Codex"}
LOG = get_logger(__name__)


def update_codex(force=False):
    """Update the package and restart everything if the version changed."""
    librarian_status_update(UPDATE_CODEX_STATUS_KEYS, 0, None)
    if force:
        LOG.info("Forcing update of Codex.")
    else:
        eau = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_AUTO_UPDATE)
        if not eau.on or not is_outdated(PACKAGE_NAME):
            librarian_status_done([UPDATE_CODEX_STATUS_KEYS])
            LOG.verbose("Codex is up to date.")
            return

        LOG.info("Codex seems outdated. Trying to update.")

    try:
        subprocess.run(
            (sys.executable, "-m", "pip", "install", "--upgrade", "codex"), check=True
        )
    except Exception as exc:
        LOG.error(exc)
        librarian_status_done([UPDATE_CODEX_STATUS_KEYS])
        return

    new_version = get_version()
    restart = VERSION != new_version

    librarian_status_done([UPDATE_CODEX_STATUS_KEYS])
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
    librarian_status_update(RESTART_CODEX_STATUS_KEYS, 0, None)
    LOG.info("Sending restart signal.")
    main_pid = os.getppid()
    os.kill(main_pid, signal.SIGUSR1)
    librarian_status_done([RESTART_CODEX_STATUS_KEYS])
