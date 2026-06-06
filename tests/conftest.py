"""Shared pytest fixtures for the Codex test suite."""

import pytest
from rest_registration.settings import registration_settings


def pytest_sessionfinish(_session, _exitstatus):
    """
    Stop the librarian/broadcast queues from hanging interpreter shutdown.

    ``LIBRARIAN_QUEUE`` and ``BROADCAST_QUEUE`` are module-level
    ``multiprocessing.Queue`` singletons. Tests put tasks on them (status
    updates, cover jobs, websocket broadcasts) but no librarian process is
    running under pytest to drain the pipe, so the queue's hidden daemon
    *feeder* thread blocks once the OS pipe buffer fills. At exit
    multiprocessing's ``atexit`` finalizer ``join()``s that feeder thread
    (``Queue._finalize_join``) and waits forever — pytest reports success,
    then the process hangs and CI never advances.

    ``cancel_join_thread()`` cancels that join so the buffered (and, in
    tests, unwanted) items are dropped and the process exits cleanly. Only
    the real librarian daemon consumes these queues, and it doesn't run
    here, so discarding the leftovers is correct.
    """
    from codex.librarian.mp_queue import LIBRARIAN_QUEUE
    from codex.websockets.mp_queue import BROADCAST_QUEUE

    for queue in (LIBRARIAN_QUEUE, BROADCAST_QUEUE):
        queue.cancel_join_thread()


@pytest.fixture(autouse=True)
def _reset_registration_settings():  # pyright: ignore[reportUnusedFunction]
    """
    Reset rest-registration's runtime settings around every test.

    ``patch_registration_setting()`` (see
    :mod:`codex.startup.registration`) swaps a fresh override dict into
    ``registration_settings`` to flip the verification / reset-password
    flows on or off at runtime. That override lives on the in-process
    settings singleton, so it outlives a Django ``TestCase`` transaction
    rollback: a test that enables the email flow would otherwise leave it
    on for every later test, breaking the ones that assert the disabled
    default 404s.

    ``reset_user_settings`` + ``reset_attr_cache`` drop the override and
    the cached attrs so each test re-reads the configured
    ``REST_REGISTRATION`` baseline — the same reset rest-registration's
    own ``setting_changed`` handler performs for ``@override_settings``.
    """
    registration_settings.reset_user_settings()
    registration_settings.reset_attr_cache()
    yield
    registration_settings.reset_user_settings()
    registration_settings.reset_attr_cache()
