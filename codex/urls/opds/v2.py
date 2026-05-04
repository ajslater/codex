"""codex:opds:v2 URL Configuration."""

from django.urls import path
from django.views.generic import RedirectView

from codex.urls.opds import opds_cached
from codex.views.opds.v2.feed import OPDS2FeedView, OPDS2StartView
from codex.views.opds.v2.manifest import OPDS2ManifestView
from codex.views.opds.v2.progression import OPDS2ProgressionView

app_name = "v2"


urlpatterns = [
    #
    # Browser
    path(
        "c/<int_list:pks>/1",
        opds_cached(OPDS2ManifestView.as_view()),
        {"group": "c", "page": 1},
        name="manifest",
    ),
    # Progression GET / PUT is correctness-sensitive — a PUT mutates
    # the bookmark, and a GET within the cache window would otherwise
    # return the pre-PUT position (multi-device sync would also see
    # stale data). cache_page only caches GETs, but the freshness
    # cost outweighs the ~9-query saving.
    path(
        "<group:group>/<int:pk>/position",
        OPDS2ProgressionView.as_view(),
        name="position",
    ),
    path(
        "<group:group>/<int_list:pks>/<int:page>",
        opds_cached(OPDS2FeedView.as_view()),
        name="feed",
    ),
    path(
        "",
        opds_cached(OPDS2StartView.as_view()),
        {"group": "r", "pks": (0,), "page": 1},
        name="start",
    ),
    path("catalog", RedirectView.as_view(pattern_name="opds:v2:start")),
]
