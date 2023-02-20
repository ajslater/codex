"""OS Signal actions."""
import asyncio
import signal
from asyncio import Event

from codex.logger.logging import get_logger

LOG = get_logger(__name__)
SIGNAL_NAMES = {"SIGINT", "SIGTERM", "SIGBREAK"}
RESTART_EVENT = Event()
SHUTDOWN_EVENT = Event()


def _shutdown_signal_handler():
    global SHUTDOWN_EVENT
    if SHUTDOWN_EVENT.is_set():
        return
    LOG.info("Asking hypercorn to shut down gracefully. Could take 10 seconds...")
    SHUTDOWN_EVENT.set()


def _restart_signal_handler():
    global RESTART_EVENT
    if RESTART_EVENT.is_set():
        return
    LOG.info("Restart signal received.")
    RESTART_EVENT.set()
    _shutdown_signal_handler()


def bind_signals_to_loop():
    """Binds signals to the handlers."""
    try:
        loop = asyncio.get_running_loop()
        for signal_name in SIGNAL_NAMES:
            sig = getattr(signal, signal_name, None)
            if sig:
                loop.add_signal_handler(sig, _shutdown_signal_handler)
        loop.add_signal_handler(signal.SIGUSR1, _restart_signal_handler)
    except NotImplementedError:
        LOG.info("Shutdown and restart signal handling not implemented on windows.")
