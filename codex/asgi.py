"""
ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``DJANGO_APPLICATION``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/
"""
from channels.routing import ProtocolTypeRouter

from codex.applications.http import HTTP_APPLICATION
from codex.applications.lifespan import LifespanApplication
from codex.applications.websocket import WEBSOCKET_APPLICATION


application = ProtocolTypeRouter(
    {
        "http": HTTP_APPLICATION,
        "websocket": WEBSOCKET_APPLICATION,
        "lifespan": LifespanApplication(),
    }
)
