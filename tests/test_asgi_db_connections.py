"""An ASGI request must release its database connections before its thread dies."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Final

import pytest
from asgiref.sync import SyncToAsync, ThreadSensitiveContext, sync_to_async
from django.db import connections
from django.http import HttpResponse, StreamingHttpResponse
from django.test import override_settings
from django.urls import path

from codex.applications.http import (
    ConnectionClosingApplication,
    PooledApplication,
    _is_bypassed,
)
from codex.applications.workers import WORKER_POOL, WorkerPool
from codex.asgi import application
from codex.librarian.db import enable_persistent_connections

_ALIAS: Final = "test_asgi_db_connections"
_PERSISTENT: Final = 600
_REQUESTS: Final = 3
_CONCURRENT: Final = 6
_WORKERS: Final = 2
_SCOPE: Final = {
    "type": "http",
    "asgi": {"version": "3.0", "spec_version": "2.1"},
    "http_version": "1.1",
    "method": "GET",
    "scheme": "http",
    "path": "/",
    "raw_path": b"/",
    "query_string": b"",
    "root_path": "",
    "headers": [(b"host", b"testserver")],
    "client": ("127.0.0.1", 12345),
    "server": ("testserver", 80),
}


def _alias_settings(tmp_path, max_age):
    """Build a file-backed alias mirroring the default database."""
    return {
        **connections.settings["default"],
        "NAME": str(tmp_path / "asgi_conn.sqlite3"),
        "CONN_MAX_AGE": max_age,
    }


@pytest.fixture
def alias(tmp_path, django_db_blocker):
    """
    Register a throwaway file-backed database for the duration of a test.

    It has to be a *file*: Django's sqlite backend makes ``close()`` a
    no-op for in-memory databases so the test database isn't destroyed
    mid-suite, which would make every assertion here vacuously pass.
    It starts at ``CONN_MAX_AGE=0`` like the real default database;
    tests that need persistence raise it themselves.

    Only the alias needs unregistering afterwards: the connection itself
    is opened on a worker thread, and each test accounts for it there.
    """
    connections.settings[_ALIAS] = _alias_settings(tmp_path, 0)
    with django_db_blocker.unblock():
        yield _ALIAS
    del connections.settings[_ALIAS]


class OrmApplication:
    """
    A miniature of Django's ``ASGIHandler``.

    It opens a database connection from inside its own
    ``ThreadSensitiveContext``, exactly as ``ASGIHandler.__call__`` does,
    and records the connection wrapper and worker thread so a test can
    inspect them after the executor backing that context is gone.
    """

    def __init__(self, alias) -> None:
        """Bind to a database alias and prepare the recordings."""
        self.alias = alias
        self.wrapper = None
        self.thread = None

    def _query(self) -> None:
        """Open the thread's connection and remember where it landed."""
        wrapper = connections[self.alias]
        with wrapper.cursor() as cursor:
            cursor.execute("SELECT 1")
        self.wrapper = wrapper
        self.thread = threading.current_thread()

    async def __call__(self, scope, receive, send) -> None:  # noqa: ARG002
        """Run the query on the request's thread-sensitive worker."""
        async with ThreadSensitiveContext():
            await sync_to_async(self._query)()


def _make_receive():
    """
    Build an ASGI ``receive`` that sends one empty body, then blocks.

    Django's handler drains the request body before doing anything else
    and then leaves ``listen_for_disconnect`` parked on ``receive``, so
    the second call must never return — the handler cancels that task
    when the response is done.
    """
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()
        raise AssertionError

    return receive


async def _send(message) -> None:
    """Discard the response."""


class Probe:
    """Records the wrapper and thread a Django view's ORM work landed on."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.wrapper = None
        self.thread = None

    def query(self) -> None:
        """Open this thread's connection to the throwaway alias."""
        wrapper = connections[_ALIAS]
        with wrapper.cursor() as cursor:
            cursor.execute("SELECT 1")
        self.wrapper = wrapper
        self.thread = threading.current_thread()


_PROBE = Probe()


def _close_orphan(wrapper) -> None:
    """
    Close a connection nothing else can reach.

    Its thread is gone, so ``wrapper.close()`` would fail
    ``validate_thread_sharing``. Leaving it open would emit the very
    ResourceWarning this module is about.
    """
    if wrapper is not None and wrapper.connection is not None:
        wrapper.connection.close()
        wrapper.connection = None


def _probe_view(_request):
    """Touch the database and return a plain response."""
    _PROBE.query()
    return HttpResponse(b"ok")


def _raising_body():
    """Yield one chunk, then fail the way a vanishing archive would."""
    yield b"chunk"
    msg = "the librarian moved the file"
    raise OSError(msg)


def _streaming_probe_view(_request):
    """Touch the database and stream a body that fails mid-transfer."""
    _PROBE.query()
    return StreamingHttpResponse(_raising_body())


urlpatterns = [
    path("probe/", _probe_view),
    path("stream/", _streaming_probe_view),
]


def _http_application() -> PooledApplication:
    """Return the application codex actually serves HTTP with."""
    app = application.application_mapping["http"]
    assert isinstance(app, PooledApplication)
    return app


def _drive_django(app, path_):
    """Run one request through a real Django handler, recording on _PROBE."""
    _PROBE.wrapper = None
    _PROBE.thread = None
    scope = {**_SCOPE, "path": path_, "raw_path": path_.encode()}
    with override_settings(ROOT_URLCONF=__name__):
        return asyncio.run(app(scope, _make_receive(), _send))


def test_web_process_has_no_persistent_connections():
    """The shipped settings leave Django's ASGI-safe default in place."""
    assert connections.settings["default"]["CONN_MAX_AGE"] == 0


def test_django_closes_the_request_connection_itself(alias):  # noqa: ARG001
    """At CONN_MAX_AGE=0 Django's own request_finished hook is enough."""
    django_app = _http_application().application
    _drive_django(django_app, "/probe/")

    assert _PROBE.thread is not None
    assert not _PROBE.thread.is_alive()
    assert _PROBE.wrapper is not None
    assert _PROBE.wrapper.connection is None


def test_django_alone_orphans_it_when_the_body_raises(alias):  # noqa: ARG001
    """The exit Django has no hook on: a streaming body that fails."""
    django_app = _http_application().application
    with pytest.raises(OSError, match="librarian moved"):
        _drive_django(django_app, "/stream/")

    assert _PROBE.thread is not None
    assert not _PROBE.thread.is_alive()
    assert _PROBE.wrapper is not None
    # Re-raised out of ASGIHandler.handle()'s TaskGroup before either
    # request_finished or response.close() runs, so nothing closed it.
    assert _PROBE.wrapper.connection is not None
    _close_orphan(_PROBE.wrapper)


def test_backstop_closes_when_the_body_raises(alias):  # noqa: ARG001
    """That is what the wrapper is for — it closes on the same worker."""
    with pytest.raises(OSError, match="librarian moved"):
        _drive_django(_http_application().unpooled, "/stream/")

    assert _PROBE.thread is not None
    assert not _PROBE.thread.is_alive()
    assert _PROBE.wrapper is not None
    assert _PROBE.wrapper.connection is None


def test_http_application_closes_request_connections(alias):
    """The wrapper closes what the request opened, on the request's thread."""
    inner = OrmApplication(alias)
    asyncio.run(ConnectionClosingApplication(inner)(_SCOPE, _make_receive(), _send))

    assert inner.thread is not None
    assert not inner.thread.is_alive()
    assert inner.wrapper is not None
    assert inner.wrapper.connection is None


def test_unwrapped_application_orphans_a_persistent_connection(alias, tmp_path):
    """``CONN_MAX_AGE>0`` under ASGI outlives its thread — the original bug."""
    connections.settings[alias] = _alias_settings(tmp_path, _PERSISTENT)
    inner = OrmApplication(alias)
    asyncio.run(inner(_SCOPE, _make_receive(), _send))

    assert inner.thread is not None
    assert not inner.thread.is_alive()
    assert inner.wrapper is not None
    assert inner.wrapper.connection is not None
    # Close it by hand: nothing else can reach it now, and leaving it
    # open would emit the very ResourceWarning this module is about.
    _close_orphan(inner.wrapper)


def test_enable_persistent_connections_is_process_scoped(alias):
    """The librarian's opt-in reaches wrappers created after the call."""
    assert connections.settings[alias]["CONN_MAX_AGE"] == 0
    enable_persistent_connections(_PERSISTENT, alias=alias)
    assert connections.settings[alias]["CONN_MAX_AGE"] == _PERSISTENT

    inner = OrmApplication(alias)
    asyncio.run(inner(_SCOPE, _make_receive(), _send))

    # ``connect()`` re-reads CONN_MAX_AGE, so the wrapper the worker built
    # after the call schedules its close 600s out rather than immediately
    # — which is why the connection is still open.
    assert inner.wrapper is not None
    assert inner.wrapper.connection is not None
    _close_orphan(inner.wrapper)


def test_asgi_http_route_is_wired():
    """The served HTTP application pools, and can fall back."""
    app = _http_application()
    assert app.pool is WORKER_POOL
    assert isinstance(app.unpooled, ConnectionClosingApplication)


class SlowOrmApplication(OrmApplication):
    """Records every thread it ran on, and dawdles so requests overlap."""

    def __init__(self, alias, delay=0.02) -> None:
        """Bind to an alias and set how long each request occupies a worker."""
        super().__init__(alias)
        self.delay = delay
        self.threads = []

    def _query(self) -> None:
        """Occupy this worker long enough for another request to queue."""
        super()._query()
        self.threads.append(threading.current_thread())
        time.sleep(self.delay)


@asynccontextmanager
async def _pool(size):
    """Start a worker pool for one test and always stop it."""
    pool = WorkerPool(size)
    await pool.start()
    try:
        yield pool
    finally:
        await pool.stop()


def test_pooled_requests_reuse_one_worker_and_connection(alias):
    """The point of the pool: the thread and its connection survive."""
    inner = SlowOrmApplication(alias, delay=0)

    async def main():
        async with _pool(1) as pool:
            app = PooledApplication(inner, pool)
            for _ in range(_REQUESTS):
                await app(_SCOPE, _make_receive(), _send)
            # Read the recordings before ``stop`` retires the worker.
            assert inner.thread is not None
            assert inner.wrapper is not None
            return inner.thread, inner.wrapper, inner.wrapper.connection

    thread, wrapper, connection = asyncio.run(main())

    assert thread.name.startswith("codex-http-db-0")
    assert len({id(t) for t in inner.threads}) == 1
    assert len(inner.threads) == _REQUESTS
    # One connection served all three requests, and it was open the
    # whole time — which is what CONN_MAX_AGE means and could not mean
    # while every request got its own thread.
    assert connection is not None
    assert wrapper.connection is None
    assert not thread.is_alive()


def test_pool_bounds_concurrency(alias):
    """A pool of two serves six concurrent requests on two threads."""
    inner = SlowOrmApplication(alias)

    async def main():
        async with _pool(_WORKERS) as pool:
            app = PooledApplication(inner, pool)
            await asyncio.gather(
                *(app(_SCOPE, _make_receive(), _send) for _ in range(_CONCURRENT))
            )

    asyncio.run(main())

    assert len(inner.threads) == _CONCURRENT
    assert len({id(t) for t in inner.threads}) == _WORKERS


def test_disabled_pool_falls_back_to_per_request_threads(alias):
    """Size 0 serves every request the way it was served before."""
    inner = OrmApplication(alias)

    async def main():
        async with _pool(0) as pool:
            assert not pool.enabled
            await PooledApplication(inner, pool)(_SCOPE, _make_receive(), _send)

    asyncio.run(main())

    assert inner.thread is not None
    assert not inner.thread.is_alive()
    assert inner.wrapper is not None
    assert inner.wrapper.connection is None


def test_failed_self_check_disables_the_pool(alias, monkeypatch):
    """If asgiref ever stops routing as we expect, nothing is pooled."""
    monkeypatch.setattr(WorkerPool, "_self_check", lambda _self: _false(), raising=True)
    inner = OrmApplication(alias)

    async def main():
        async with _pool(_WORKERS) as pool:
            assert not pool.enabled
            await PooledApplication(inner, pool)(_SCOPE, _make_receive(), _send)

    asyncio.run(main())

    assert inner.thread is not None
    assert not inner.thread.is_alive()
    assert inner.wrapper is not None
    assert inner.wrapper.connection is None


async def _false() -> bool:
    """Stand in for a self-check that fails."""
    return False


def test_stop_closes_a_busy_worker(alias):
    """A request still in flight at shutdown keeps its worker, then frees it."""
    inner = SlowOrmApplication(alias, delay=0.3)
    pool = WorkerPool(1)

    async def main():
        await pool.start()
        app = PooledApplication(inner, pool)
        request = asyncio.create_task(app(_SCOPE, _make_receive(), _send))
        # Stop while the request still holds the worker.
        await asyncio.sleep(0.05)
        await asyncio.gather(pool.stop(), request)

    asyncio.run(main())

    assert inner.wrapper is not None
    assert inner.wrapper.connection is None
    assert inner.thread is not None
    assert not inner.thread.is_alive()


def test_asgiref_still_routes_onto_a_seeded_context():
    """
    Pin the asgiref behavior the pool is built on.

    The pool installs a context asgiref would otherwise create lazily.
    That is two non-underscored class attributes and a documented
    re-entrancy guarantee, none of it a promised API — so assert it
    directly. A failure here explains a pool that silently disabled
    itself.
    """

    async def main():
        context = ThreadSensitiveContext()
        executor = ThreadPoolExecutor(max_workers=1)
        SyncToAsync.context_to_thread_executor[context] = executor
        try:
            expected = executor.submit(threading.get_ident).result(5)
            token = SyncToAsync.thread_sensitive_context.set(context)
            try:
                # Django's own inner block must be a re-entrant no-op.
                async with ThreadSensitiveContext() as inner_context:
                    assert inner_context.token is None
                    return expected, await sync_to_async(threading.get_ident)()
            finally:
                SyncToAsync.thread_sensitive_context.reset(token)
        finally:
            SyncToAsync.context_to_thread_executor.pop(context, None)
            executor.shutdown()

    expected, actual = asyncio.run(main())
    assert actual == expected


def test_downloads_and_health_bypass_the_pool():
    """Requests that would hold a worker for a transfer are exempt."""
    assert _is_bypassed({"path": "/health"})
    assert _is_bypassed({"path": "/api/v4/comics/1/download/book.cbz"})
    assert _is_bypassed({"path": "/api/v4/browse/publishers/1/download/all.cbz"})
    assert _is_bypassed({"path": "/opds/bin/c/1/download/book.cbz"})
    assert _is_bypassed({"path": "/read/1/book.pdf"})
    assert not _is_bypassed({"path": "/api/v4/auth/csrf"})
    assert not _is_bypassed({"path": "/no/such/route"})
    # The url path prefix is stripped before resolving.
    assert _is_bypassed({"path": "/codex/health", "root_path": "/codex"})


def test_a_worker_can_be_returned_after_the_pool_is_stopped(monkeypatch):
    """A request that outlasts the shutdown wait must not break on release."""
    monkeypatch.setattr(WorkerPool, "STOP_TIMEOUT", 0.01)
    pool = WorkerPool(1)

    async def main():
        await pool.start()
        # Shut down while the only worker is checked out. ``stop`` gives
        # up waiting for it, resets the pool, and the request then hands
        # a worker back to a pool that no longer has a queue.
        async with pool.acquire():
            await pool.stop()

    asyncio.run(main())

    assert not pool.enabled
