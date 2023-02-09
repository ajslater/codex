"""HTPP router for using a channels endpoint."""
from channels.routing import URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path, re_path

from codex.applications.websocket import ROOT_PREFIX
from codex.consumers.send import SendConsumer


HTTP_APPLICATION = URLRouter(
    [
        path(f"{ROOT_PREFIX}send", SendConsumer().as_asgi()),  # type: ignore
        re_path(r"", get_asgi_application()),  # type: ignore
    ]
)
