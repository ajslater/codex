"""Update the codex python package."""
import os
import signal
import subprocess
import sys

from logging import getLogger

from codex.models import AdminFlag
from codex.version import PACKAGE_NAME, VERSION, get_version, is_outdated


LOG = getLogger(__name__)


def update_codex(force=False):
    """Update the package and restart everything if the version changed."""
    if force:
        LOG.info("Forcing update of Codex.")
    else:
        eau = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_AUTO_UPDATE)
        if not eau.on or not is_outdated(PACKAGE_NAME):
            return

        LOG.info("Codex seems outdated. Trying to update.")

    try:
        subprocess.check_call(
            (sys.executable, "-m", "pip", "install", "--upgrade", "codex")
        )
    except Exception as exc:
        LOG.error(exc)
        return

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
    LOG.info("Sending restart signal.")
    main_pid = os.getppid()
    os.kill(main_pid, signal.SIGUSR1)
