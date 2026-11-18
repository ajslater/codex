"""codex:api:v4:shelves URL Configuration."""

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.shelves import ShelfDetailView, ShelfItemsView, ShelfListView

app_name = "shelves"
urlpatterns = [
    path("", never_cache(ShelfListView.as_view()), name="list"),
    path("<int:pk>", never_cache(ShelfDetailView.as_view()), name="detail"),
    path("<int:pk>/items", never_cache(ShelfItemsView.as_view()), name="items"),
]
