"""An ASGI request must release its database connections before its thread dies."""

import asyncio
import threading
from typing import Final

import pytest
from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.db import connections
from django.http import HttpResponse, StreamingHttpResponse
from django.test import override_settings
from django.urls import path

from codex.applications.http import ConnectionClosingApplication
from codex.asgi import application
from codex.librarian.db import enable_persistent_connections

_ALIAS: Final = "test_asgi_db_connections"
_PERSISTENT: Final = 600
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


def _http_application() -> ConnectionClosingApplication:
    """Return the application codex actually serves HTTP with."""
    app = application.application_mapping["http"]
    assert isinstance(app, ConnectionClosingApplication)
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
        _drive_django(_http_application(), "/stream/")

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


def test_asgi_http_route_is_wrapped():
    """The served HTTP application is the connection-closing one."""
    assert _http_application().application is not None
