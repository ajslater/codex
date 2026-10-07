"""
``CoverThread.stop()`` shuts the render pool down on every supported Python.

``ProcessPoolExecutor.terminate_workers()`` only exists on 3.14+. ``stop()``
called it unconditionally, so on the declared 3.12 floor (and 3.13)
stopping the librarian raised ``AttributeError``.
"""

from threading import Lock
from unittest.mock import MagicMock

from loguru import logger

from codex.librarian.covers.coverd import CoverThread
from codex.librarian.mp_queue import LIBRARIAN_QUEUE


def _thread_with_pool(pool: MagicMock | None) -> CoverThread:
    thread = CoverThread(logger, LIBRARIAN_QUEUE, Lock())
    thread._cover_pool = pool  # noqa: SLF001
    return thread


def test_stop_terminates_workers_when_available() -> None:
    """3.14+: SIGTERM in-flight workers, then reap the pool."""
    pool = MagicMock(spec_set=["terminate_workers", "shutdown"])
    thread = _thread_with_pool(pool)

    thread.stop()

    pool.terminate_workers.assert_called_once_with()
    pool.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    assert thread._cover_pool is None  # noqa: SLF001


def test_stop_without_terminate_workers() -> None:
    """3.12/3.13: no ``terminate_workers``; cancel pending work and reap."""
    pool = MagicMock(spec_set=["shutdown"])
    thread = _thread_with_pool(pool)

    thread.stop()

    pool.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    assert thread._cover_pool is None  # noqa: SLF001


def test_stop_without_pool_only_signals_shutdown() -> None:
    """A thread that never rendered has no pool to tear down."""
    thread = _thread_with_pool(None)

    thread.stop()

    assert thread.queue.get_nowait() == CoverThread.SHUTDOWN_MSG
    assert thread.queue.empty()
    assert thread._cover_pool is None  # noqa: SLF001
