"""codex:opds:v1 URL Configuration."""
from django.urls import path

from codex.views.opds.util import full_redirect_view
from codex.views.opds.v2.feed import OPDS2FeedView

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
    path("", full_redirect_view("opds:v2:feed"), name="start"),
]
