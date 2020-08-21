"""
ASGI Lifespan protocol application.

https://asgi.readthedocs.io/en/latest/specs/lifespan.html
"""
import logging

from asgiref.sync import sync_to_async

from codex.librarian.daemon import start_daemons
from codex.librarian.daemon import stop_daemons


LOG = logging.getLogger(__name__)


async def lifespan_application(scope, receive, send):
    """Lifespan application."""
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                await sync_to_async(start_daemons)()
                await send({"type": "lifespan.startup.complete"})
            except Exception as exc:
                LOG.error(exc)
                await send({"type": "lifespan.startup.failed"})
        elif message["type"] == "lifespan.shutdown":
            try:
                await sync_to_async(stop_daemons)()
                await send({"type": "lifespan.shutdown.complete"})
            except Exception as exc:
                LOG.error(exc)
                await send({"type": "lifespan.startup.failed"})
            break
