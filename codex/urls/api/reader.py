"""codex:api:v3:reader URL Configuration."""

from django.urls import path
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.vary import vary_on_cookie

from codex.urls.const import COVER_MAX_AGE, PAGE_MAX_AGE, READER_TIMEOUT
from codex.views.browser.cover import CoverView
from codex.views.download import DownloadView
from codex.views.reader.page import ReaderPageView
from codex.views.reader.reader import ReaderView
from codex.views.reader.settings import ReaderSettingsView

app_name = "issue"
urlpatterns = [
    #
    #
    # Reader
    path(
        "<int:pk>",
        # The reader endpoint serves per-user state (bookmark, settings,
        # arc context). ``vary_on_cookie`` scopes the cache key per
        # session so per-user responses don't leak; ``cache_page``
        # amortizes the full pipeline across tab refreshes / mobile-app
        # re-foreground (reader perf plan Tier 1 #3).
        cache_page(READER_TIMEOUT)(vary_on_cookie(ReaderView.as_view())),
        name="reader",
    ),
    path(
        "<int:pk>/<int:page>/page.jpg",
        cache_control(max_age=PAGE_MAX_AGE, public=True)(ReaderPageView.as_view()),
        name="page",
    ),
    path(
        "<int:pk>/cover.webp",
        # Server-side `cache_page` wraps the HTTP cache_control so the
        # response (including Cache-Control + Vary: Cookie) is cached and
        # replayed without re-running the ACL pipeline. `vary_on_cookie`
        # is essential: it adds Vary: Cookie to the response BEFORE
        # cache_page's process_response stores it, so the cache key is
        # keyed per session. Without it, cache_page would serve one
        # user's cover to every user who hits the same URL.
        cache_page(COVER_MAX_AGE)(
            cache_control(max_age=COVER_MAX_AGE, public=True)(
                vary_on_cookie(CoverView.as_view())
            )
        ),
        name="cover",
    ),
    path("settings", ReaderSettingsView.as_view(), name="settings"),
    path(
        "<int:pk>/settings",
        ReaderSettingsView.as_view(),
        name="comic_settings",
    ),
    #
    #
    # Download
    path(
        "<int:pk>/download/<str:filename>",
        DownloadView.as_view(),
        name="download",
    ),
]
