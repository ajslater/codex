"""codex:app URL Configuration."""
from django.urls import path, re_path, register_converter

from codex.urls.converters import GroupConverter
from codex.views.frontend import IndexView


app_name = "app"

register_converter(GroupConverter, "group")

urlpatterns = [
    path("<group:group>/<int:pk>/<int:page>", IndexView.as_view(), name="route"),
    path("error/<int:code>", IndexView.as_view(), name="error"),
    path("", IndexView.as_view(), name="start"),
    # This makes outside deep linking into the vue router app work
    re_path(".*", IndexView.as_view(), name="catchall"),
]
