"""codex:opds:v1 URL Configuration."""

from django.urls import path

from codex.urls.opds import opds_cached
from codex.views.opds.opensearch.v1 import OpenSearch1View
from codex.views.opds.v1.feed import OPDS1FeedView, OPDS1StartView

app_name = "v1"


urlpatterns = [
    #
    # Browser
    path(
        "<group:group>/<int_list:pks>/<int:page>",
        opds_cached(OPDS1FeedView.as_view()),
        name="feed",
    ),
    path(
        "opensearch/v1.1",
        opds_cached(OpenSearch1View.as_view()),
        name="opensearch_v1",
    ),
    # Start
    path(
        "",
        opds_cached(OPDS1StartView.as_view()),
        {"group": "r", "pks": (0,), "page": 1},
        name="start",
    ),
]
