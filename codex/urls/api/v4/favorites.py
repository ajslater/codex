"""codex:api:v4:favorites URL Configuration."""

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.v4.favorites import V4FavoriteDetailView, V4FavoritesListView

app_name = "favorites"
urlpatterns = [
    path("", never_cache(V4FavoritesListView.as_view()), name="list"),
    path(
        "<collection:collection>/<int:target_id>",
        never_cache(V4FavoriteDetailView.as_view()),
        name="detail",
    ),
]
