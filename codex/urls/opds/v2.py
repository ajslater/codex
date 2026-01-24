"""codex:opds:v1 URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView

from codex.urls.const import OPDS_TIMEOUT
from codex.views.opds.v2.feed import OPDS2FeedView, OPDS2StartView
from codex.views.opds.v2.manifest import OPDS2ManifestView
from codex.views.opds.v2.progression import OPDS2ProgressionView

app_name = "v2"

urlpatterns = [
    #
    # Browser
    path(
        "c/<int_list:pks>/1",
        cache_page(OPDS_TIMEOUT)(OPDS2ManifestView.as_view()),
        {"group": "c", "page": 1},
        name="manifest",
    ),
    path(
        "<group:group>/<int:pk>/position",
        cache_page(OPDS_TIMEOUT)(OPDS2ProgressionView.as_view()),
        name="position",
    ),
    path(
        "<group:group>/<int_list:pks>/<int:page>",
        cache_page(OPDS_TIMEOUT)(OPDS2FeedView.as_view()),
        name="feed",
    ),
    path(
        "",
        cache_page(OPDS_TIMEOUT)(OPDS2StartView.as_view()),
        {"group": "r", "pks": (0,), "page": 1},
        name="start",
    ),
    path("catalog", RedirectView.as_view(pattern_name="opds:v2:start")),
]
