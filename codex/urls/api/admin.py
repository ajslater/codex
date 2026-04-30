"""codex:api:v3:admin URL Configuration."""

from types import MappingProxyType
from typing import Final

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.admin.age_rating_metron import AdminAgeRatingMetronViewSet
from codex.views.admin.api_key import AdminAPIKey
from codex.views.admin.flag import AdminFlagViewSet
from codex.views.admin.group import AdminGroupViewSet
from codex.views.admin.library import (
    AdminFailedImportViewSet,
    AdminFolderListView,
    AdminLibraryViewSet,
)
from codex.views.admin.stats import AdminStatsView
from codex.views.admin.tasks import (
    AdminLibrarianStatusViewSet,
    AdminLibrarianTaskView,
)
from codex.views.admin.user import AdminUserChangePasswordView, AdminUserViewSet

READ: Final = MappingProxyType({"get": "list"})
# Async list action exposed by ``adrf`` viewsets; same dispatch shape
# as ``READ`` but routes the GET to ``alist`` instead of ``list`` so the
# request stays on the event loop.
AREAD: Final = MappingProxyType({"get": "alist"})
RETRIEVE: Final = MappingProxyType({"get": "retrieve"})
CREATE: Final = MappingProxyType({"post": "create"})
UPDATE: Final = MappingProxyType({"put": "partial_update"})
DELETE: Final = MappingProxyType({"delete": "destroy"})

app_name = "admin"
urlpatterns = [
    path(
        "user",
        AdminUserViewSet.as_view({**CREATE, **READ}),
        name="user_read",
    ),
    path(
        "user/<int:pk>/",
        AdminUserViewSet.as_view({**UPDATE, **DELETE}),
        name="user_update_delete",
    ),
    path(
        "user/<int:pk>/password",
        AdminUserChangePasswordView.as_view(),
        name="user_password_update",
    ),
    path("group", AdminGroupViewSet.as_view({**CREATE, **READ}), name="group"),
    path(
        "group/<int:pk>/",
        AdminGroupViewSet.as_view({**UPDATE, **DELETE}),
        name="group_update",
    ),
    path("flag", AdminFlagViewSet.as_view({**READ}), name="flag"),
    path(
        "flag/<str:key>/",
        AdminFlagViewSet.as_view({**RETRIEVE, **UPDATE}),
        name="one_flag",
    ),
    path(
        "library",
        AdminLibraryViewSet.as_view({**CREATE, **READ}),
        name="library",
    ),
    path(
        "library/<int:pk>/",
        AdminLibraryViewSet.as_view({**UPDATE, **DELETE}),
        name="library",
    ),
    path("folders", AdminFolderListView.as_view(), name="folders"),
    path(
        "failed-import",
        AdminFailedImportViewSet.as_view({**READ}),
        name="failed_import",
    ),
    path(
        "librarian/status",
        never_cache(AdminLibrarianStatusViewSet.as_view({**AREAD}, active_only=True)),
        name="librarian_status",
    ),
    path(
        "librarian/status/all",
        never_cache(AdminLibrarianStatusViewSet.as_view({**AREAD})),
        name="librarian_status_all",
    ),
    path("librarian/task", AdminLibrarianTaskView.as_view(), name="librarian_task"),
    path("stats", AdminStatsView.as_view(), name="stats"),
    path("api_key", AdminAPIKey.as_view(), name="api_key"),
    path(
        "age-rating-metron",
        AdminAgeRatingMetronViewSet.as_view({**READ}),
        name="age_rating_metron",
    ),
]
