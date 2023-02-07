"""Channels Websocket Application."""
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from codex.consumers.notifier import NotifierConsumer


websocket_application = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(
            [
                # TODO figure out root_path
                path("codex/api/v3/ws", NotifierConsumer.as_asgi()),
            ]
        )
    )
)
