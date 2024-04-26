"""codex:api:v3:browser URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_page, never_cache

from codex.urls.const import BROWSER_TIMEOUT, PAGE_MAX_AGE
from codex.views.bookmark import BookmarkView
from codex.views.browser.browser import BrowserView
from codex.views.browser.choices import BrowserChoicesAvailableView, BrowserChoicesView
from codex.views.browser.metadata import MetadataView
from codex.views.browser.session import BrowserSessionView

METADATA_TIMEOUT = PAGE_MAX_AGE

app_name = "browser"
urlpatterns = [
    #
    #
    # Browser
    path(
        "<int_list:pks>/<int:page>",
        cache_page(BROWSER_TIMEOUT)(BrowserView.as_view()),
        name="page",
    ),
    path(
        "<int_list:pks>/choices/<str:field_name>",
        cache_page(BROWSER_TIMEOUT)(BrowserChoicesView.as_view()),
        name="choices_field",
    ),
    path(
        "<int_list:pks>/choices_available",
        cache_page(BROWSER_TIMEOUT)(BrowserChoicesAvailableView.as_view()),
        name="choices_available",
    ),
    path(
        "<int_list:pks>/metadata",
        cache_page(METADATA_TIMEOUT)(MetadataView.as_view()),
        name="metadata",
    ),
    #
    #
    # Bookmark
    path(
        "<int_list:pks>/bookmark",
        BookmarkView.as_view(),
        name="bookmark",
    ),
    path("settings", never_cache(BrowserSessionView.as_view()), name="settings"),
]
