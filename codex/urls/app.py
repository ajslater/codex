"""codex:app URL Configuration."""

from django.urls import path, re_path
from django.views.decorators.cache import cache_page

from codex.urls.root import TIMEOUT
from codex.views.download import FileView
from codex.views.frontend import IndexView

app_name = "app"

urlpatterns = [
    path("<group:group>/<int:pk>/<int:page>", IndexView.as_view(), name="route"),
    path("c/<int:pk>/book.pdf", cache_page(TIMEOUT)(FileView.as_view()), name="pdf"),
    path("error/<int:code>", IndexView.as_view(), name="error"),
    path("", IndexView.as_view(), name="start"),
    # This makes outside deep linking into the vue router app work
    re_path(".*", IndexView.as_view(), name="catchall"),
]
