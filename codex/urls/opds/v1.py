"""codex:opds:v1 URL Configuration."""

from django.urls import path

from codex.urls.opds import opds_cached
from codex.views.opds.opensearch.v1 import OpenSearch1View
from codex.views.opds.v1.feed import OPDS1FeedView, OPDS1StartView

app_name = "v1"


urlpatterns = [
    #
    # Browser. Two patterns share the ``feed`` name: a collection root
    # listing (no parent ids) and a scoped listing. ``page`` is the
    # ``?page=`` query param (read via ``AuthMixin`` / ``requires_page``).
    path(
        "<collection:collection>",
        opds_cached(OPDS1FeedView.as_view()),
        name="feed",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>",
        opds_cached(OPDS1FeedView.as_view()),
        name="feed",
    ),
    path(
        "opensearch/v1.1",
        opds_cached(OpenSearch1View.as_view()),
        name="opensearch_v1",
    ),
    # Start (catalog root; resolves to the top collection, no parent ids).
    path(
        "",
        opds_cached(OPDS1StartView.as_view()),
        {"group": "root", "pks": (), "page": 1},
        name="start",
    ),
]
