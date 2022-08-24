"""codex:app URL Configuration."""
from django.urls import path

from codex.views.frontend import IndexView


app_name = "app"

urlpatterns = [
    path("<str:group>/<int:pk>/<int:page>", IndexView.as_view(), name="route"),
    path("error/<int:code>", IndexView.as_view(), name="error"),
    path("", IndexView.as_view(), name="start"),
]
