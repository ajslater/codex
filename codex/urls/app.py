"""codex:app URL Configuration."""

from typing import Final

from django.urls import path, re_path
from django.views.generic import RedirectView

from codex.views.download import FileView
from codex.views.frontend import IndexView
from codex.views.util import cache_control_2xx

app_name = "app"

BOOK_AGE: Final = 60 * 60 * 24 * 7

urlpatterns = [
    # v4 collection-based SPA routes. ``IndexView`` ignores the URL kwargs
    # (it only serves the SPA shell + injects last_route); these patterns
    # exist so deep links / refreshes on the new URLs serve the app instead
    # of hitting the catch-all redirect. ``page`` is a ``?page=`` query param.
    path("<collection:collection>", IndexView.as_view(), name="browser_root"),
    path(
        "<collection:collection>/<int_list:parent_ids>",
        IndexView.as_view(),
        name="browser",
    ),
    path("read/<int:pk>", IndexView.as_view(), name="reader"),
    path(
        "read/<int:pk>/book.pdf",
        cache_control_2xx(max_age=BOOK_AGE)(FileView.as_view()),
        name="reader_pdf",
    ),
    path(
        "c/<int:pk>/book.pdf",
        cache_control_2xx(max_age=BOOK_AGE)(FileView.as_view()),
        name="pdf",
    ),
    path("admin/<str:tab>", IndexView.as_view(), name="admin"),
    path("error/<int:code>", IndexView.as_view(), name="error"),
    # Client-side auth route reached from an emailed link. Must serve the SPA
    # so Vue Router can render the reset screen; without it the catch-all below
    # would redirect the link to the home page.
    path("auth/reset-password/", IndexView.as_view(), name="reset-password"),
    # Client-side auth route reached from the OIDC adapter's error
    # redirects (codex/oidc.py). Same catch-all hazard as reset-password.
    path("auth/sso-error", IndexView.as_view(), name="sso-error"),
    path("", IndexView.as_view(), name="start"),
    re_path(
        ".*",
        RedirectView.as_view(pattern_name="app:start", permanent=False),
        name="catchall",
    ),
]
