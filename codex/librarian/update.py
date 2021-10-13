"""Update the codex python package."""
import logging
import os
import signal
import subprocess
import sys

from codex.librarian.latest_version import get_installed_version, is_outdated
from codex.models import AdminFlag
from codex.settings.settings import CACHE_PATH


LOG = logging.getLogger(__name__)
PACKAGE_NAME = "codex"


def update_codex(force=False):
    """Update the package and restart everything if the version changed."""
    if not force:
        eau = AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_AUTO_UPDATE)
        if not eau.on:
            return False

        if not is_outdated(PACKAGE_NAME, cache_root=CACHE_PATH):
            return False

        LOG.info("Codex seems outdated. Trying to update.")
    else:
        LOG.info("Forcing update of Codex.")

    old_version = get_installed_version(PACKAGE_NAME, parse=True)
    try:
        subprocess.check_call(
            (sys.executable, "-m", "pip", "install", "--upgrade", "codex")
        )
    except Exception as exc:
        LOG.error(exc)
        return False

    new_version = get_installed_version(PACKAGE_NAME, parse=True)

    restart = old_version != new_version
    if restart:
        LOG.info("Codex was updated.")
        restart_codex()
    else:
        LOG.warn("Codex updated to the same version that was previously installed.")


def restart_codex():
    """Send a system SIGUSR1 signal as handled in run.py."""
    LOG.info("Sending restart signal.")
    main_pid = os.getppid()
    os.kill(main_pid, signal.SIGUSR1)
