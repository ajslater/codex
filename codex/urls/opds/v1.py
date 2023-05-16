"""codex:opds:v1 URL Configuration."""
from django.urls import path
from django.views.decorators.cache import cache_page

from codex.views.opds.util import full_redirect_view
from codex.views.opds.v1.feed import OPDS1FeedView
from codex.views.opds.v1.opensearch_v1 import OpenSearch1View

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
    path(
        "opensearch/v1.1",
        cache_page(TIMEOUT)(OpenSearch1View.as_view()),
        name="opensearch_v1",
    ),
    #
    # Catch All
    path("", full_redirect_view("opds:v1:feed"), name="start"),
]
