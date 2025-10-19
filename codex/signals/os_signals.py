"""OS Signal actions."""

import asyncio
import signal
from asyncio import Event
from sys import platform

from loguru import logger

STOP_SIGNAL_NAMES = (
    "SIGABRT",
    "SIGBREAK",
    "SIGBUS",
    "SIGHUP",
    "SIGINT",
    "SIGQUIT",
    "SIGSEGV",
    "SIGTERM",
    "SIGUSR2",
)
RESTART_SIGNAL_NAMES = ("SIGUSR1",)
RESTART_EVENT = Event()
SHUTDOWN_EVENT = Event()


def _shutdown_signal_handler(*_args):
    """Initiate Codex Shutdown."""
    if SHUTDOWN_EVENT.is_set():
        return
    logger.info("Asking hypercorn to shut down gracefully. Could take 10 seconds...")
    SHUTDOWN_EVENT.set()


def _restart_signal_handler(*_args):
    """Initiate Codex Restart."""
    if RESTART_EVENT.is_set():
        return
    logger.info("Restart signal received.")
    RESTART_EVENT.set()
    _shutdown_signal_handler()


def bind_signals_to_loop_aux(sig_add, signal_names, handler):
    """Bind signal names to a handler."""
    for name in signal_names:
        if sig := getattr(signal, name, None):
            sig_add(sig, handler)


def bind_signals_to_loop():
    """Binds signals to the handlers."""
    try:
        if platform == "win32":
            sig_add = signal.signal
        else:
            loop = asyncio.get_running_loop()
            sig_add = loop.add_signal_handler
        bind_signals_to_loop_aux(sig_add, STOP_SIGNAL_NAMES, _shutdown_signal_handler)
        bind_signals_to_loop_aux(sig_add, RESTART_SIGNAL_NAMES, _restart_signal_handler)
    except NotImplementedError:
        logger.info("Shutdown and restart signal handling not implemented on windows.")
