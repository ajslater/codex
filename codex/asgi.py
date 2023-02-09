"""
ASGI config for codex project.

It exposes the ASGI callable as a module-level variable named ``DJANGO_APPLICATION``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/
"""
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path, re_path

from codex.applications.lifespan import LifespanApplication
from codex.applications.websocket import ROOT_PREFIX, websocket_application
from codex.consumers.send import SendConsumer


application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                # TODO root_path
                # TODO can i use path?
                re_path(rf"^{ROOT_PREFIX}send", SendConsumer().as_asgi()),
                re_path(r"", get_asgi_application()),
            ]
        ),
        "websocket": websocket_application,
        "lifespan": LifespanApplication(),
    }
)
