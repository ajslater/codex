"""Channels Websocket Application."""

from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from codex.settings import FEATURES
from codex.websockets.consumers import NotifierConsumer
from codex.websockets.v4_consumers import V4NotifierConsumer

_ROUTES = [
    path(  # pyright:ignore[reportCallIssue]
        "api/v3/ws",
        NotifierConsumer.as_asgi(),  # pyright: ignore[reportArgumentType]
        name="websocket",
    ),
]
if FEATURES.api_v4:
    _ROUTES.append(
        path(  # pyright:ignore[reportCallIssue]
            "api/v4/ws",
            V4NotifierConsumer.as_asgi(),  # pyright: ignore[reportArgumentType]
            name="websocket_v4",
        )
    )

WEBSOCKET_APPLICATION = AllowedHostsOriginValidator(
    AuthMiddlewareStack(URLRouter(_ROUTES))
)
