"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page

from codex.urls.const import BROWSER_TIMEOUT
from codex.views.opds.util import full_redirect_view
from codex.views.opds.v2.feed import OPDS2FeedView
from codex.views.opds.v2.progression import OPDS2ProgressionView

app_name = "v2"

urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int_list:pks>/<int:page>",
        cache_page(BROWSER_TIMEOUT)(OPDS2FeedView.as_view()),
        name="feed",
    ),
    path(
        "c/<str:pk>/<int:page>",
        cache_page(BROWSER_TIMEOUT)(OPDS2FeedView.as_view()),
        name="acq",
    ),
    path(
        "<group:group>/<int:pk>/position",
        cache_page(BROWSER_TIMEOUT)(OPDS2ProgressionView.as_view()),
        name="position",
    ),
    #
    # Catch All
    path("", full_redirect_view("opds:v2:feed"), name="start"),
]
