"""Channels Websocket Application."""
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from codex.consumers.notifier import NotifierConsumer
from codex.settings.settings import HYPERCORN_CONFIG


# channels is ignorant of root_path
# https://github.com/django/channels/issues/1973
_PREFIX = HYPERCORN_CONFIG.root_path[1:] + "/" if HYPERCORN_CONFIG.root_path else ""

websocket_application = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(
            [
                path(
                    f"{_PREFIX}api/v3/ws",
                    NotifierConsumer.as_asgi(),  # type: ignore
                    name="websocket",
                ),
            ]
        )
    )
)
