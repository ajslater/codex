"""codex:api:v4:admin URL Configuration."""

from types import MappingProxyType
from typing import Final

from django.urls import path
from django.views.decorators.cache import never_cache

from codex.views.v4.admin import (
    V4AdminAgeRatingsViewSet,
    V4AdminAPIKeyView,
    V4AdminCustomCoverBulkDeleteView,
    V4AdminCustomCoverDeleteView,
    V4AdminCustomCoverListView,
    V4AdminCustomCoverUploadView,
    V4AdminEmailSettingsView,
    V4AdminEmailTestSendView,
    V4AdminFailedImportViewSet,
    V4AdminFlagViewSet,
    V4AdminFoldersView,
    V4AdminGroupViewSet,
    V4AdminIdentifierURLView,
    V4AdminLibraryViewSet,
    V4AdminStatsView,
    V4AdminTaggingDefaultsView,
    V4AdminTaggingValidateView,
    V4AdminTagSessionAbortView,
    V4AdminTagSessionPromptResponseView,
    V4AdminTagSessionPromptsView,
    V4AdminTagSessionsCreateView,
    V4AdminTagSessionSkipAllView,
    V4AdminTagSessionsListView,
    V4AdminTagWritePreflightView,
    V4AdminTagWriteView,
    V4AdminTasksCreateView,
    V4AdminTasksListView,
    V4AdminThrottleSettingsView,
    V4AdminUserDataExportView,
    V4AdminUserDataImportView,
    V4AdminUserPasswordView,
    V4AdminUserSendVerificationView,
    V4AdminUserViewSet,
)

# ViewSet action dispatch maps — match the v3 admin URL conf so
# the inherited methods (list/create/partial_update/destroy)
# resolve correctly under the v4 subclass.
READ: Final = MappingProxyType({"get": "list"})
AREAD: Final = MappingProxyType({"get": "alist"})
RETRIEVE: Final = MappingProxyType({"get": "retrieve"})
CREATE: Final = MappingProxyType({"post": "create"})
UPDATE: Final = MappingProxyType({"patch": "partial_update"})
DELETE: Final = MappingProxyType({"delete": "destroy"})

app_name = "admin"
urlpatterns = [
    # Users
    path(
        "users",
        V4AdminUserViewSet.as_view({**READ, **CREATE}),
        name="users",
    ),
    path(
        "users/<int:pk>",
        V4AdminUserViewSet.as_view({**RETRIEVE, **UPDATE, **DELETE}),
        name="user",
    ),
    path(
        "users/<int:pk>/password",
        V4AdminUserPasswordView.as_view(),
        name="user_password",
    ),
    path(
        "users/<int:pk>/send-verification",
        V4AdminUserSendVerificationView.as_view(),
        name="user_send_verification",
    ),
    # Groups
    path(
        "groups",
        V4AdminGroupViewSet.as_view({**READ, **CREATE}),
        name="groups",
    ),
    path(
        "groups/<int:pk>",
        V4AdminGroupViewSet.as_view({**RETRIEVE, **UPDATE, **DELETE}),
        name="group",
    ),
    # Libraries
    path(
        "libraries",
        V4AdminLibraryViewSet.as_view({**READ, **CREATE}),
        name="libraries",
    ),
    path(
        "libraries/<int:pk>",
        V4AdminLibraryViewSet.as_view({**RETRIEVE, **UPDATE, **DELETE}),
        name="library",
    ),
    # Flags
    path(
        "flags",
        V4AdminFlagViewSet.as_view({**READ}),
        name="flags",
    ),
    path(
        "flags/<str:key>",
        V4AdminFlagViewSet.as_view({**RETRIEVE, **UPDATE}),
        name="flag",
    ),
    # Failed imports
    path(
        "failed-imports",
        V4AdminFailedImportViewSet.as_view({**READ}),
        name="failed_imports",
    ),
    # Age ratings (read-only Metron lookup)
    path(
        "age-ratings",
        V4AdminAgeRatingsViewSet.as_view({**READ}),
        name="age_ratings",
    ),
    # Custom covers
    path(
        "custom-covers",
        V4AdminCustomCoverListView.as_view(),
        name="custom_covers_list",
    ),
    path(
        "custom-covers/upload",
        V4AdminCustomCoverUploadView.as_view(),
        name="custom_covers_upload",
    ),
    path(
        "custom-covers/bulk-delete",
        V4AdminCustomCoverBulkDeleteView.as_view(),
        name="custom_covers_bulk_delete",
    ),
    path(
        "custom-covers/<int:pk>",
        V4AdminCustomCoverDeleteView.as_view(),
        name="custom_cover_detail",
    ),
    # Singletons / config
    path(
        "email-settings",
        V4AdminEmailSettingsView.as_view(),
        name="email_settings",
    ),
    path(
        "email-settings/test",
        V4AdminEmailTestSendView.as_view(),
        name="email_settings_test",
    ),
    path(
        "tagging-defaults",
        V4AdminTaggingDefaultsView.as_view(),
        name="tagging_defaults",
    ),
    path(
        "tagging-defaults/validate",
        V4AdminTaggingValidateView.as_view(),
        name="tagging_defaults_validate",
    ),
    path(
        "throttle-settings",
        V4AdminThrottleSettingsView.as_view(),
        name="throttle_settings",
    ),
    path(
        "stats",
        V4AdminStatsView.as_view(),
        name="stats",
    ),
    path(
        "api-key",
        V4AdminAPIKeyView.as_view(),
        name="api_key",
    ),
    # Librarian tasks
    path(
        "tasks",
        never_cache(V4AdminTasksListView.as_view({**AREAD})),
        name="tasks_list",
    ),
    path(
        "tasks/run",
        V4AdminTasksCreateView.as_view(),
        name="tasks_run",
    ),
    # Online tagging (renamed tag-sessions in v4)
    path(
        "tag-sessions",
        V4AdminTagSessionsListView.as_view(),
        name="tag_sessions_list",
    ),
    path(
        "tag-sessions/start",
        V4AdminTagSessionsCreateView.as_view(),
        name="tag_sessions_start",
    ),
    path(
        "tag-sessions/<str:session_id>",
        V4AdminTagSessionAbortView.as_view(),
        name="tag_session_abort",
    ),
    path(
        "tag-sessions/<str:session_id>/skip-all",
        V4AdminTagSessionSkipAllView.as_view(),
        name="tag_session_skip_all",
    ),
    path(
        "tag-sessions/<str:session_id>/prompts",
        V4AdminTagSessionPromptsView.as_view(),
        name="tag_session_prompts",
    ),
    path(
        "tag-sessions/<str:session_id>/prompts/<str:fingerprint>",
        V4AdminTagSessionPromptResponseView.as_view(),
        name="tag_session_prompt_response",
    ),
    # Misc admin actions
    path(
        "identifier-url",
        V4AdminIdentifierURLView.as_view(),
        name="identifier_url",
    ),
    path(
        "tag-write/preflight",
        V4AdminTagWritePreflightView.as_view(),
        name="tag_write_preflight",
    ),
    path(
        "tag-write",
        V4AdminTagWriteView.as_view(),
        name="tag_write",
    ),
    path(
        "folders",
        V4AdminFoldersView.as_view(),
        name="folders",
    ),
    path(
        "user-data/export",
        V4AdminUserDataExportView.as_view(),
        name="user_data_export",
    ),
    path(
        "user-data/import",
        V4AdminUserDataImportView.as_view(),
        name="user_data_import",
    ),
]
