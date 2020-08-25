"""
ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""
import os

from logging import getLogger

from django.core.asgi import get_asgi_application

from codex.lifespan import lifespan_application
from codex.websocket_server import websocket_application


LOG = getLogger()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")
# os.environ['PYTHONASYNCIODEBUG'] = "1"

django_application = get_asgi_application()


async def application(scope, receive, send):
    """Provide different application for different protocols."""
    LOG.debug(
        f"{scope.get('client', [None])[0]} {scope.get('type')} {scope.get('path')}"
    )
    if scope["type"] == "http":
        await django_application(scope, receive, send)
    elif scope["type"] == "websocket":
        await websocket_application(scope, receive, send)
    elif scope["type"] == "lifespan":
        await lifespan_application(scope, receive, send)
    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")
