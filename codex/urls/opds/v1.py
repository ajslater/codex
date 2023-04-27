"""codex:opds:v1 URL Configuration."""
from django.urls import path

from codex.views.opds.v1.browser import OPDS1BrowserView
from codex.views.opds.v1.start import opds_1_start_view

TIMEOUT = 60 * 60

app_name = "v1"


urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int:pk>/<int:page>",
        OPDS1BrowserView.as_view(),
        name="browser",
    ),
    #
    # Catch All
    path("", opds_1_start_view, name="start"),
]
