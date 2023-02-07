"""
ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``DJANGO_APPLICATION``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/
"""
from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

from codex.applications.lifespan import LifespanApplication
from codex.applications.websocket import websocket_application


application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": websocket_application,
        "lifespan": LifespanApplication(),
    }
)
