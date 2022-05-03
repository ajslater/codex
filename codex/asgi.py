"""
ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""
import os

import django

from django.core.asgi import get_asgi_application

from codex.signals import connect_signals


# Must setup up the django environment before importing django models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")
# os.environ["PYTHONASYNCIODEBUG"] = "1"
connect_signals()
django.setup()

from codex.lifespan import lifespan_application  # noqa: E402
from codex.websocket_server import websocket_application  # noqa: E402


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
