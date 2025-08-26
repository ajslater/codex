"""Channels Websocket Application."""

from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from codex.websockets.consumers import NotifierConsumer

WEBSOCKET_APPLICATION = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(
            [
                path(  # pyright:ignore[reportCallIssue]
                    "api/v3/ws",
                    NotifierConsumer.as_asgi(),  # pyright: ignore[reportArgumentType]
                    name="websocket",
                ),
            ]
        )
    )
)
