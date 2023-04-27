"""codex:opds:v1 URL Configuration."""
from django.urls import path

from codex.views.opds.v2.feed import OPDS2FeedView
from codex.views.opds.v2.start import opds_2_start_view

app_name = "v2"

urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int:pk>/<int:page>",
        OPDS2FeedView.as_view(),
        name="feed",
    ),
    #
    # Catch All
    path("", opds_2_start_view, name="start"),
]
