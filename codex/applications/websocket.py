"""Channels Websocket Application."""

from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from codex.settings.settings import ROOT_PATH
from codex.websockets.consumers import NotifierConsumer

# channels is ignorant of root_path
# https://github.com/django/channels/issues/1973
ROOT_PREFIX = ROOT_PATH[1:] + "/" if ROOT_PATH else ""


WEBSOCKET_APPLICATION = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(
            [
                path(
                    f"{ROOT_PREFIX}api/v3/ws",
                    NotifierConsumer.as_asgi(),
                    name="websocket",
                ),
            ]
        )
    )
)
