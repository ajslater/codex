"""
HTTP ASGI application.

Serves requests on pooled workers that keep a warm database connection,
falling back to a per-request thread whose connections are released
before it is destroyed.
"""

from functools import cache

from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.core.asgi import get_asgi_application
from django.db import connections
from django.urls import Resolver404, resolve

from codex.applications.workers import WORKER_POOL


class ConnectionClosingApplication:
    """
    Close what Django's own end-of-request hook cannot reach.

    Django's ``ASGIHandler`` runs each request's synchronous ORM work in
    a ``ThreadSensitiveContext``, which asgiref backs with a *private*
    ``ThreadPoolExecutor(max_workers=1)`` that is shut down when the
    request ends. ``django.db.connections`` is thread-local, so a
    connection left open when that thread is retired is orphaned until
    the garbage collector emits ``ResourceWarning: unclosed database``.

    With ``CONN_MAX_AGE=0`` (see ``codex.settings``) Django closes the
    connection itself on the paths it controls: ``handle()`` awaits
    ``sync_to_async(response.close)()`` — or, when the client
    disconnected, ``request_finished.asend()`` — and both dispatch
    ``close_old_connections`` onto the request's own worker. On those
    paths the ``finally`` below is a no-op costing one thread hop.

    When the worker pool is running this process opts into persistent
    connections, and a bypassed request is back on a throwaway thread —
    so for those the ``finally`` closes the connection on every path,
    not just the abnormal one.

    It also covers the exit Django has no hook on. ``send_response``
    runs inside ``handle()``'s ``TaskGroup``; if it raises anything
    other than ``RequestProcessed``/``RequestAborted`` the exception
    group is re-raised before either close runs. A streaming response's
    body is consumed *there*, outside the middleware chain, so an
    iterator that raises is never converted to a 500 — and codex streams
    comic archives straight off a user's library, where the librarian
    can move or truncate a file mid-download. The ASGI ``send``
    callable raising a transport error lands the same way.

    Entering ``ThreadSensitiveContext`` here rather than letting
    ``ASGIHandler`` open its own is what makes that cleanup reachable.
    The context manager is re-entrant and only the outermost block owns
    the executor, so Django's inner ``async with`` becomes a no-op and
    the worker thread outlives the request just long enough for the
    ``sync_to_async`` below — thread sensitive, so it lands on that same
    worker — to close what the request opened.
    """

    def __init__(self, application) -> None:
        """Wrap the Django ASGI application."""
        self.application = application

    async def __call__(self, scope, receive, send) -> None:
        """Serve one request, then release its database connections."""
        async with ThreadSensitiveContext():
            try:
                await self.application(scope, receive, send)
            finally:
                await sync_to_async(connections.close_all)()


@cache
def _bypass_views() -> tuple[frozenset, tuple[type, ...]]:
    """
    Return the views that must not hold a pooled worker.

    Imported on first use, not at module scope: this module is imported
    to build the ASGI application, which is what calls ``django.setup``.
    """
    from codex.views.browser.download import CollectionDownloadView
    from codex.views.download import DownloadView
    from codex.views.healthcheck import health_check_view

    return frozenset({health_check_view}), (DownloadView, CollectionDownloadView)


def _is_bypassed(scope) -> bool:
    """
    Decide whether a request should skip the worker pool.

    A pooled request holds its worker until its response is sent, so a
    file download would hold one for as long as the client takes to
    receive it. The health check is exempt for the opposite reason:
    it touches no database at all, and a container's health must not
    depend on the pool having a free worker.
    """
    path = scope.get("path", "")
    root_path = scope.get("root_path", "")
    if root_path and path.startswith(root_path):
        path = path[len(root_path) :]
    if not path.startswith("/"):
        path = "/" + path
    try:
        match = resolve(path)
    except Resolver404:
        # Django will answer this with a 404. Pool it like anything else.
        return False
    views, view_classes = _bypass_views()
    if match.func in views:
        return True
    view_class = getattr(match.func, "view_class", None)
    return view_class is not None and issubclass(view_class, view_classes)


class PooledApplication:
    """
    Serve requests on a pooled worker when there is one to lend.

    Pooled requests skip ``ConnectionClosingApplication`` deliberately:
    their worker outlives them, so the connection it holds is meant to
    be reused by the next request rather than closed. Django's own
    ``close_old_connections`` still recycles it on age or error, exactly
    as it does for a WSGI worker thread.
    """

    def __init__(self, application, pool) -> None:
        """Wrap the Django ASGI application and bind the worker pool."""
        self.application = application
        self.pool = pool
        self.unpooled = ConnectionClosingApplication(application)

    async def __call__(self, scope, receive, send) -> None:
        """Serve one request, pooled if the pool has a worker for it."""
        if self.pool.enabled and not _is_bypassed(scope):
            async with self.pool.acquire():
                await self.application(scope, receive, send)
        else:
            await self.unpooled(scope, receive, send)


HTTP_APPLICATION = PooledApplication(get_asgi_application(), WORKER_POOL)
