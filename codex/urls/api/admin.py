"""codex:api:v3:admin URL Configuration."""
from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.admin import LibrarianStatusViewSet, QueueLibrarianJobs


app_name = "admin"
urlpatterns = [
    path("queue_job", QueueLibrarianJobs.as_view(), name="queue_job"),
    path(
        "librarian_status",
        never_cache(LibrarianStatusViewSet.as_view({"get": "list"})),
        name="librarian_status",
    ),
]
