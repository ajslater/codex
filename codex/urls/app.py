"""codex:app URL Configuration."""

from django.urls import path, re_path
from django.views.decorators.cache import cache_control

from codex.views.download import FileView
from codex.views.frontend import IndexView

app_name = "app"

BOOK_AGE = 60 * 60 * 24 * 7

urlpatterns = [
    path("<group:group>/<int:pk>/<int:page>", IndexView.as_view(), name="route"),
    path(
        "c/<int:pk>/book.pdf",
        cache_control(max_age=BOOK_AGE)(FileView.as_view()),
        name="pdf",
    ),
    path("error/<int:code>", IndexView.as_view(), name="error"),
    path("", IndexView.as_view(), name="start"),
    # This makes outside deep linking into the vue router app work
    re_path(".*", IndexView.as_view(), name="catchall"),
]
