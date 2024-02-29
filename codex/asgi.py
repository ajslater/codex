"""ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``DJANGO_APPLICATION``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/
"""

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

from codex.applications.lifespan import LifespanApplication
from codex.applications.websocket import WEBSOCKET_APPLICATION
from codex.logger.mp_queue import LOG_QUEUE
from codex.websockets.aio_queue import BROADCAST_QUEUE

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": WEBSOCKET_APPLICATION,
        "lifespan": LifespanApplication(LOG_QUEUE, BROADCAST_QUEUE),
    }
)
