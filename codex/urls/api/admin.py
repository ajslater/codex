"""codex:api:v3:admin URL Configuration."""

from django.urls import path
from django.views.decorators.cache import never_cache

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

READ = {"get": "list"}
CREATE = {"post": "create"}
UPDATE = {"put": "partial_update"}
DELETE = {"delete": "destroy"}

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
        name="user_update_delete",
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
        AdminFlagViewSet.as_view({**UPDATE}),
        name="flag_update",
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
        never_cache(AdminLibrarianStatusViewSet.as_view({**READ})),
        name="librarian_status",
    ),
    path("librarian/task", AdminLibrarianTaskView.as_view(), name="librarian_task"),
    path("stats", AdminStatsView.as_view(), name="stats"),
    path("api_key", AdminAPIKey.as_view(), name="api_key"),
]
