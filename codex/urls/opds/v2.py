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
    # Browser. The manifest keeps its literal ``c/`` prefix (it never
    # used the group converter); its pks are always real comic pks.
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
    # cost outweighs the ~9-query saving. Comic-only: the ``group``
    # default lets the existing ``{group: "c", pk}`` reverse match.
    path(
        "comics/<int:pk>/position",
        OPDS2ProgressionView.as_view(),
        {"group": "c"},
        name="position",
    ),
    # Two patterns share the ``feed`` name: a collection root listing
    # (no parent ids) and a scoped listing. ``page`` is ``?page=``.
    path(
        "<collection:collection>",
        opds_cached(OPDS2FeedView.as_view()),
        name="feed",
    ),
    path(
        "<collection:collection>/<int_list:parent_ids>",
        opds_cached(OPDS2FeedView.as_view()),
        name="feed",
    ),
    path(
        "",
        opds_cached(OPDS2StartView.as_view()),
        {"group": "r", "pks": (), "page": 1},
        name="start",
    ),
    path("catalog", RedirectView.as_view(pattern_name="opds:v2:start")),
]
