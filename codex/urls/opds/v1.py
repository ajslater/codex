"""codex:opds:v1 URL Configuration."""
from django.urls import path

from codex.views.opds.v1.feed import OPDS1FeedView
from codex.views.opds.v1.start import opds_1_start_view

TIMEOUT = 60 * 60

app_name = "v1"


urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int:pk>/<int:page>",
        OPDS1FeedView.as_view(),
        name="feed",
    ),
    #
    # Catch All
    path("", opds_1_start_view, name="start"),
]
