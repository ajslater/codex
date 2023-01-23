"""
ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``DJANGO_APPLICATION``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/
"""
from django.core.asgi import get_asgi_application

from codex.lifespan import lifespan_application
from codex.websocket_server import websocket_application


DJANGO_APPLICATION = get_asgi_application()


async def application(scope, receive, send):
    """Provide different application for different protocols."""
    if scope["type"] == "http":
        await DJANGO_APPLICATION(scope, receive, send)
    elif scope["type"] == "websocket":
        await websocket_application(scope, receive, send)
    elif scope["type"] == "lifespan":
        await lifespan_application(scope, receive, send)
    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")
