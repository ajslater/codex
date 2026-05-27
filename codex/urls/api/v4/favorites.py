"""codex:api:v4:favorites URL Configuration."""

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.favorites import FavoriteDetailView, FavoriteListView

app_name = "favorites"
urlpatterns = [
    path("", never_cache(FavoriteListView.as_view()), name="list"),
    path(
        "<collection:collection>/<int:target_id>",
        never_cache(FavoriteDetailView.as_view()),
        name="detail",
    ),
]
