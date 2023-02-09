from channels.routing import URLRouter
from django.core.asgi import get_asgi_application
from django.urls import re_path

from codex.applications.websocket import ROOT_PREFIX
from codex.consumers.send import SendConsumer


HTTP_APPLICATION = URLRouter(
    [
        # TODO can i use path?
        re_path(rf"^{ROOT_PREFIX}send", SendConsumer().as_asgi()),
        re_path(r"", get_asgi_application()),
    ]
)
