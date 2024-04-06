"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page

from codex.urls.const import BROWSER_TIMEOUT
from codex.views.opds.util import full_redirect_view
from codex.views.opds.v2.feed import OPDS2FeedView

app_name = "v2"

urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<str:pks>/<int:page>",
        cache_page(BROWSER_TIMEOUT)(OPDS2FeedView.as_view()),
        name="feed",
    ),
    #
    # Catch All
    path("", full_redirect_view("opds:v2:feed"), name="start"),
]
