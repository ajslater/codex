"""Channels Websocket Application."""
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from codex.settings.settings import HYPERCORN_CONFIG
from codex.websockets.consumers import NotifierConsumer

# channels is ignorant of root_path
# https://github.com/django/channels/issues/1973
ROOT_PREFIX = HYPERCORN_CONFIG.root_path[1:] + "/" if HYPERCORN_CONFIG.root_path else ""


WEBSOCKET_APPLICATION = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(
            [
                path(
                    f"{ROOT_PREFIX}api/v3/ws",
                    NotifierConsumer.as_asgi(),  # type: ignore
                    name="websocket",
                ),
            ]
        )
    )
)
