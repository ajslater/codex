"""OS Signal actions."""

import asyncio
import signal
from asyncio import Event
from sys import platform
from typing import Final

from loguru import logger

STOP_SIGNAL_NAMES: Final = (
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
RESTART_SIGNAL_NAMES: Final = ("SIGUSR1",)
RESTART_EVENT = Event()
SHUTDOWN_EVENT = Event()


def _shutdown_signal_handler(*_args) -> None:
    """Initiate Codex Shutdown."""
    if SHUTDOWN_EVENT.is_set():
        return
    logger.info("Asking granian to shut down gracefully. Could take 10 seconds...")
    SHUTDOWN_EVENT.set()


def _restart_signal_handler(*_args) -> None:
    """Initiate Codex Restart."""
    if RESTART_EVENT.is_set():
        return
    logger.info("Restart signal received.")
    RESTART_EVENT.set()
    _shutdown_signal_handler()


def bind_signals_to_loop_aux(sig_add, signal_names, handler) -> None:
    """Bind signal names to a handler."""
    for name in signal_names:
        if sig := getattr(signal, name, None):
            sig_add(sig, handler)


def bind_signals_to_loop() -> None:
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
