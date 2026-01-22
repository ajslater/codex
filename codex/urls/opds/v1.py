"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page

from codex.urls.const import OPDS_TIMEOUT
from codex.views.opds.v1.feed import OPDS1FeedView, OPDS1StartView
from codex.views.opds.v1.opensearch_v1 import OpenSearch1View

app_name = "v1"


urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int_list:pks>/<int:page>",
        cache_page(OPDS_TIMEOUT)(OPDS1FeedView.as_view()),
        name="feed",
    ),
    path(
        "opensearch/v1.1",
        cache_page(OPDS_TIMEOUT)(OpenSearch1View.as_view()),
        name="opensearch_v1",
    ),
    # Start
    path(
        "",
        cache_page(OPDS_TIMEOUT)(OPDS1StartView.as_view()),
        {"group": "r", "pks": (0,), "page": 1},
        name="start",
    ),
]
