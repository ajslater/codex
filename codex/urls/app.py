"""codex:app URL Configuration."""

from django.urls import path, re_path
from django.views.decorators.cache import cache_control
from django.views.generic import RedirectView

from codex.views.download import FileView
from codex.views.frontend import IndexView

app_name = "app"

BOOK_AGE = 60 * 60 * 24 * 7

urlpatterns = [
    path("<group:group>/<int_list:pks>/<int:page>", IndexView.as_view(), name="route"),
    path(
        "c/<int:pk>/book.pdf",
        cache_control(max_age=BOOK_AGE)(FileView.as_view()),
        name="pdf",
    ),
    path("admin/<str:tab>", IndexView.as_view(), name="admin"),
    path("error/<int:code>", IndexView.as_view(), name="error"),
    path("", IndexView.as_view(), name="start"),
    re_path(
        ".*",
        RedirectView.as_view(pattern_name="app:start", permanent=False),
        name="catchall",
    ),
]
