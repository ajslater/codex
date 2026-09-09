"""
HTTP ASGI application.

Wraps Django's ASGI handler so every request releases its database
connections before the thread that opened them is destroyed.
"""

from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.core.asgi import get_asgi_application
from django.db import connections


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

    It exists for the exit Django has no hook on. ``send_response``
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


HTTP_APPLICATION = ConnectionClosingApplication(get_asgi_application())
