"""codex:opds:v1 URL Configuration."""
from django.urls import path
from django.views.decorators.cache import cache_page

from codex.views.opds.opensearch import OpenSearchView

TIMEOUT = 60 * 60

app_name = "opensearch"


urlpatterns = [
    path(
        "/1.1",
        cache_page(TIMEOUT)(OpenSearchView.as_view()),
        name="1.1",
    ),
]
