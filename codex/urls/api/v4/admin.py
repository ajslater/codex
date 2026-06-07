"""codex:api:v4:admin URL Configuration."""

from types import MappingProxyType
from typing import Final

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.admin.age_rating_metron import AdminAgeRatingMetronViewSet
from codex.views.admin.api_key import AdminAPIKey
from codex.views.admin.custom_cover import (
    AdminCustomCoverDeleteView,
    AdminCustomCoverListView,
    AdminCustomCoverRemoveView,
    AdminCustomCoverUploadView,
)
from codex.views.admin.dump_user_data import AdminDumpUserDataView
from codex.views.admin.email import AdminEmailSettingsView, AdminEmailTestSendView
from codex.views.admin.failed_imports_seen import AdminFailedImportsSeenView
from codex.views.admin.flag import AdminFlagViewSet
from codex.views.admin.group import AdminGroupViewSet
from codex.views.admin.library import (
    AdminFailedImportViewSet,
    AdminFolderListView,
    AdminLibraryViewSet,
)
from codex.views.admin.onlinetag import (
    AdminOnlineTagAbortView,
    AdminOnlineTagActiveView,
    AdminOnlineTagPromptResponseView,
    AdminOnlineTagPromptsView,
    AdminOnlineTagSkipAllPromptsView,
    AdminOnlineTagStartView,
)
from codex.views.admin.restore_user_data import (
    AdminRestoreUserDataView,
    AdminUserDataBackupsView,
)
from codex.views.admin.stats import AdminStatsView
from codex.views.admin.tag_write_errors import AdminTagWriteErrorsView
from codex.views.admin.tagging_defaults import AdminTaggingDefaultsView
from codex.views.admin.tagging_validate import AdminTaggingValidateView
from codex.views.admin.tagwrite import (
    AdminParseIdentifierURLView,
    AdminTagWritePreflightView,
    AdminTagWriteView,
)
from codex.views.admin.tasks import AdminLibrarianStatusViewSet, AdminLibrarianTaskView
from codex.views.admin.throttle import AdminThrottleSettingsView
from codex.views.admin.user import (
    AdminUserBulkView,
    AdminUserChangePasswordView,
    AdminUserSendVerificationView,
    AdminUserViewSet,
)

READ: Final = MappingProxyType({"get": "list"})
AREAD: Final = MappingProxyType({"get": "alist"})
RETRIEVE: Final = MappingProxyType({"get": "retrieve"})
CREATE: Final = MappingProxyType({"post": "create"})
UPDATE: Final = MappingProxyType({"patch": "partial_update"})
DELETE: Final = MappingProxyType({"delete": "destroy"})

app_name = "admin"
urlpatterns = [
    path(
        "users",
        AdminUserViewSet.as_view({**READ, **CREATE}),
        name="users",
    ),
    path(
        "users/<int:pk>",
        AdminUserViewSet.as_view({**RETRIEVE, **UPDATE, **DELETE}),
        name="user",
    ),
    path(
        "users/<int:pk>/password",
        AdminUserChangePasswordView.as_view(),
        name="user_password",
    ),
    path(
        "users/<int:pk>/send-verification",
        AdminUserSendVerificationView.as_view(),
        name="user_send_verification",
    ),
    path(
        "users/bulk",
        AdminUserBulkView.as_view(),
        name="users_bulk",
    ),
    path(
        "groups",
        AdminGroupViewSet.as_view({**READ, **CREATE}),
        name="groups",
    ),
    path(
        "groups/<int:pk>",
        AdminGroupViewSet.as_view({**RETRIEVE, **UPDATE, **DELETE}),
        name="group",
    ),
    path(
        "libraries",
        AdminLibraryViewSet.as_view({**READ, **CREATE}),
        name="libraries",
    ),
    path(
        "libraries/<int:pk>",
        AdminLibraryViewSet.as_view({**RETRIEVE, **UPDATE, **DELETE}),
        name="library",
    ),
    path(
        "flags",
        AdminFlagViewSet.as_view({**READ}),
        name="flags",
    ),
    path(
        "flags/<str:key>",
        AdminFlagViewSet.as_view({**RETRIEVE, **UPDATE}),
        name="flag",
    ),
    path(
        "failed-imports",
        AdminFailedImportViewSet.as_view({**READ}),
        name="failed_imports",
    ),
    path(
        "failed-imports/seen",
        AdminFailedImportsSeenView.as_view(),
        name="failed_imports_seen",
    ),
    path(
        "age-ratings",
        AdminAgeRatingMetronViewSet.as_view({**READ}),
        name="age_ratings",
    ),
    path(
        "custom-covers",
        AdminCustomCoverListView.as_view(),
        name="custom_covers_list",
    ),
    path(
        "custom-covers/upload",
        AdminCustomCoverUploadView.as_view(),
        name="custom_covers_upload",
    ),
    path(
        "custom-covers/bulk-delete",
        AdminCustomCoverRemoveView.as_view(),
        name="custom_covers_bulk_delete",
    ),
    path(
        "custom-covers/<int:pk>",
        AdminCustomCoverDeleteView.as_view(),
        name="custom_cover_detail",
    ),
    path(
        "email-settings",
        AdminEmailSettingsView.as_view(),
        name="email_settings",
    ),
    path(
        "email-settings/test",
        AdminEmailTestSendView.as_view(),
        name="email_settings_test",
    ),
    path(
        "tagging-defaults",
        AdminTaggingDefaultsView.as_view(),
        name="tagging_defaults",
    ),
    path(
        "tagging-defaults/validate",
        AdminTaggingValidateView.as_view(),
        name="tagging_defaults_validate",
    ),
    path(
        "throttle-settings",
        AdminThrottleSettingsView.as_view(),
        name="throttle_settings",
    ),
    path(
        "stats",
        AdminStatsView.as_view(),
        name="stats",
    ),
    path(
        "api-key",
        AdminAPIKey.as_view(),
        name="api_key",
    ),
    # Librarian tasks. /tasks is active-only (sidebar progress feed);
    # /tasks/all is the full history (Jobs tab).
    path(
        "tasks",
        never_cache(AdminLibrarianStatusViewSet.as_view({**AREAD}, active_only=True)),
        name="tasks_list",
    ),
    path(
        "tasks/all",
        never_cache(AdminLibrarianStatusViewSet.as_view({**AREAD})),
        name="tasks_list_all",
    ),
    path(
        "tasks/run",
        AdminLibrarianTaskView.as_view(),
        name="tasks_run",
    ),
    # Online tagging. The scan ("tag-session") is the live Pass-1 lookup;
    # deferred prompts persist independently and are addressed by fingerprint.
    path(
        "tag-sessions",
        AdminOnlineTagActiveView.as_view(),
        name="tag_sessions_list",
    ),
    path(
        "tag-sessions/start",
        AdminOnlineTagStartView.as_view(),
        name="tag_sessions_start",
    ),
    path(
        "tag-sessions/<str:session_id>",
        AdminOnlineTagAbortView.as_view(),
        name="tag_session_abort",
    ),
    path(
        "tag-prompts",
        AdminOnlineTagPromptsView.as_view(),
        name="tag_prompts",
    ),
    path(
        "tag-prompts/skip-all",
        AdminOnlineTagSkipAllPromptsView.as_view(),
        name="tag_prompts_skip_all",
    ),
    path(
        "tag-prompts/<str:fingerprint>",
        AdminOnlineTagPromptResponseView.as_view(),
        name="tag_prompt_response",
    ),
    path(
        "identifier-url",
        AdminParseIdentifierURLView.as_view(),
        name="identifier_url",
    ),
    path(
        "tag-write/preflight",
        AdminTagWritePreflightView.as_view(),
        name="tag_write_preflight",
    ),
    path(
        "tag-write/errors",
        AdminTagWriteErrorsView.as_view(),
        name="tag_write_errors",
    ),
    path(
        "tag-write",
        AdminTagWriteView.as_view(),
        name="tag_write",
    ),
    path(
        "folders",
        AdminFolderListView.as_view(),
        name="folders",
    ),
    path(
        "user-data/export",
        AdminDumpUserDataView.as_view(),
        name="user_data_export",
    ),
    path(
        "user-data/backups",
        never_cache(AdminUserDataBackupsView.as_view()),
        name="user_data_backups",
    ),
    path(
        "user-data/import",
        AdminRestoreUserDataView.as_view(),
        name="user_data_import",
    ),
]
