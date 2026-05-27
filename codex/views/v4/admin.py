"""
API v4 admin endpoints — thin envelope wrappers over v3.

The plan calls for JSON:API on admin (sparse fieldsets, includes,
relationships). That's a deep per-serializer rewrite that lands as a
follow-up; this commit ships the v4 URL contract end-to-end against
the v3 view bodies so the URL surface and envelope wire shape are
stable while the JSON:API serializer migration proceeds resource-by-
resource. The JSON:API renderer dependency is already pinned (see
``pyproject.toml``) so the migration can flip on per viewset without
another infrastructure pass.

The frontend admin store now drives /api/v4/admin/* directly; the
v3 store is gone with the rest of v3.
"""

from rest_framework.response import Response

from codex.views.admin.age_rating_metron import AdminAgeRatingMetronViewSet
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.api_key import AdminAPIKey
from codex.views.admin.custom_cover import (
    AdminCustomCoverDeleteView,
    AdminCustomCoverListView,
    AdminCustomCoverRemoveView,
    AdminCustomCoverUploadView,
)
from codex.views.admin.dump_user_data import AdminDumpUserDataView
from codex.views.admin.email import AdminEmailSettingsView, AdminEmailTestSendView
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
from codex.views.admin.restore_user_data import AdminRestoreUserDataView
from codex.views.admin.stats import AdminStatsView
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
    AdminUserChangePasswordView,
    AdminUserSendVerificationView,
    AdminUserViewSet,
)
from codex.views.v4.common import EnvelopeJSONRenderer, V4CursorPagination


class _V4AdminMixin:
    """All v4 admin endpoints wear the envelope renderer.

    ``pagination_class`` is the v4 cursor paginator: viewset list
    actions return ``{count?, next, previous, results}`` (the
    standard DRF pagination shape) inside the envelope's ``data``
    slot. APIViews ignore the attribute. The page-number paginator
    stays in use for browser endpoints, where the UI surfaces an
    explicit page-N control.
    """

    renderer_classes = (EnvelopeJSONRenderer,)
    pagination_class = V4CursorPagination


# ── Resources (CRUD) ────────────────────────────────────────────────


class V4AdminUserViewSet(_V4AdminMixin, AdminUserViewSet):
    """``/api/v4/admin/users`` + ``/api/v4/admin/users/{id}``."""


class V4AdminUserPasswordView(_V4AdminMixin, AdminUserChangePasswordView):
    """``POST /api/v4/admin/users/{id}/password``."""


class V4AdminUserSendVerificationView(_V4AdminMixin, AdminUserSendVerificationView):
    """``POST /api/v4/admin/users/{id}/send-verification``."""


class V4AdminUserBulkView(_V4AdminMixin, AdminAPIView):
    """
    Apply a batch admin action to multiple users.

    ``POST /api/v4/admin/users/bulk``.
    Body: ``{"action": "delete", "ids": [int, ...]}``. Returns
    ``{"deleted": [int], "skipped": [{id, reason}]}``. ``delete`` is
    the only action today; other actions can land here later
    (deactivate, set-staff, etc.) without changing the URL.
    """

    def post(self, request, *_args, **_kwargs) -> Response:
        """Apply the bulk action."""
        from rest_framework.exceptions import ValidationError as DRFValidationError

        from codex.librarian.notifier.tasks import users_changed_task
        from codex.models import User as UserModel

        action = request.data.get("action")
        ids_raw = request.data.get("ids") or []
        if action != "delete":
            msg = f"Unsupported bulk action {action!r}; only 'delete' is allowed."
            raise DRFValidationError({"action": msg})
        if not isinstance(ids_raw, list) or not ids_raw:
            raise DRFValidationError({"ids": "Provide a non-empty list of user ids."})
        try:
            ids = [int(pk) for pk in ids_raw]
        except (TypeError, ValueError) as exc:
            raise DRFValidationError({"ids": "All ids must be integers."}) from exc

        current_user_id = getattr(request.user, "pk", None)
        deleted: list[int] = []
        skipped: list[dict] = []
        for pk in ids:
            if pk == current_user_id:
                skipped.append({"id": pk, "reason": "self"})
                continue
            try:
                user = UserModel.objects.get(pk=pk)
            except UserModel.DoesNotExist:
                skipped.append({"id": pk, "reason": "not_found"})
                continue
            user.delete()
            deleted.append(pk)
        if deleted:
            from codex.librarian.mp_queue import LIBRARIAN_QUEUE

            LIBRARIAN_QUEUE.put(users_changed_task(ids=deleted))
        return Response({"deleted": deleted, "skipped": skipped})


class V4AdminGroupViewSet(_V4AdminMixin, AdminGroupViewSet):
    """``/api/v4/admin/groups`` + ``/api/v4/admin/groups/{id}``."""


class V4AdminLibraryViewSet(_V4AdminMixin, AdminLibraryViewSet):
    """``/api/v4/admin/libraries`` + ``/api/v4/admin/libraries/{id}``."""


class V4AdminFlagViewSet(_V4AdminMixin, AdminFlagViewSet):
    """``/api/v4/admin/flags`` + ``/api/v4/admin/flags/{key}``."""


class V4AdminFailedImportViewSet(_V4AdminMixin, AdminFailedImportViewSet):
    """``/api/v4/admin/failed-imports``."""


class V4AdminAgeRatingsViewSet(_V4AdminMixin, AdminAgeRatingMetronViewSet):
    """``GET /api/v4/admin/age-ratings`` — read-only canonical Metron table."""


# ── Custom covers (URL shape reshuffled for v4) ─────────────────────


class V4AdminCustomCoverListView(_V4AdminMixin, AdminCustomCoverListView):
    """``GET /api/v4/admin/custom-covers``."""


class V4AdminCustomCoverUploadView(_V4AdminMixin, AdminCustomCoverUploadView):
    """``POST /api/v4/admin/custom-covers``."""


class V4AdminCustomCoverDeleteView(_V4AdminMixin, AdminCustomCoverDeleteView):
    """``DELETE /api/v4/admin/custom-covers/{id}``."""


class V4AdminCustomCoverBulkDeleteView(_V4AdminMixin, AdminCustomCoverRemoveView):
    """``POST /api/v4/admin/custom-covers/bulk-delete`` — alias for v3 remove."""


# ── Singletons / config ─────────────────────────────────────────────


class V4AdminEmailSettingsView(_V4AdminMixin, AdminEmailSettingsView):
    """``GET|PATCH /api/v4/admin/email-settings``."""


class V4AdminEmailTestSendView(_V4AdminMixin, AdminEmailTestSendView):
    """``POST /api/v4/admin/email-settings/test``."""


class V4AdminTaggingDefaultsView(_V4AdminMixin, AdminTaggingDefaultsView):
    """``GET|PATCH /api/v4/admin/tagging-defaults``."""


class V4AdminTaggingValidateView(_V4AdminMixin, AdminTaggingValidateView):
    """``POST /api/v4/admin/tagging-defaults/validate``."""


class V4AdminThrottleSettingsView(_V4AdminMixin, AdminThrottleSettingsView):
    """``GET|PATCH /api/v4/admin/throttle-settings``."""


class V4AdminStatsView(_V4AdminMixin, AdminStatsView):
    """``GET /api/v4/admin/stats``."""


class V4AdminAPIKeyView(_V4AdminMixin, AdminAPIKey):
    """
    ``GET|POST /api/v4/admin/api-key`` — POST regenerates.

    v3 used PUT for regeneration; the plan switches to POST for
    consistency with other "create-or-replace" admin actions.
    """

    def post(self, *args, **kwargs) -> Response:
        """POST is the v4 spelling of regenerate; reuse the v3 PUT path."""
        return self.put(*args, **kwargs)


# ── Librarian tasks ─────────────────────────────────────────────────


class V4AdminTasksListView(_V4AdminMixin, AdminLibrarianStatusViewSet):
    """``GET /api/v4/admin/tasks`` — librarian status list."""


class V4AdminTasksCreateView(_V4AdminMixin, AdminLibrarianTaskView):
    """``POST /api/v4/admin/tasks`` — enqueue a librarian task."""


# ── Online tagging (v3 ``online-tag/*`` → v4 ``tag-sessions/*``) ────


class V4AdminTagSessionsListView(_V4AdminMixin, AdminOnlineTagActiveView):
    """``GET /api/v4/admin/tag-sessions`` — active session ID, if any."""


class V4AdminTagSessionsCreateView(_V4AdminMixin, AdminOnlineTagStartView):
    """``POST /api/v4/admin/tag-sessions``."""


class V4AdminTagSessionAbortView(_V4AdminMixin, AdminOnlineTagAbortView):
    """``DELETE /api/v4/admin/tag-sessions/{id}``."""

    def delete(self, request, *args, **kwargs) -> Response:
        """v4 DELETE = v3 POST abort."""
        return self.post(request, *args, **kwargs)


class V4AdminTagSessionSkipAllView(_V4AdminMixin, AdminOnlineTagSkipAllPromptsView):
    """``POST /api/v4/admin/tag-sessions/{id}/skip-all``."""


class V4AdminTagSessionPromptsView(_V4AdminMixin, AdminOnlineTagPromptsView):
    """``GET /api/v4/admin/tag-sessions/{id}/prompts``."""


class V4AdminTagSessionPromptResponseView(
    _V4AdminMixin, AdminOnlineTagPromptResponseView
):
    """``POST /api/v4/admin/tag-sessions/{id}/prompts/{fingerprint}``."""


# ── Misc admin actions ──────────────────────────────────────────────


class V4AdminIdentifierURLView(_V4AdminMixin, AdminParseIdentifierURLView):
    """``POST /api/v4/admin/identifier-url``."""


class V4AdminTagWritePreflightView(_V4AdminMixin, AdminTagWritePreflightView):
    """``POST /api/v4/admin/tag-write/preflight``."""


class V4AdminTagWriteView(_V4AdminMixin, AdminTagWriteView):
    """``POST /api/v4/admin/tag-write``."""


class V4AdminFoldersView(_V4AdminMixin, AdminFolderListView):
    """``GET /api/v4/admin/folders?path=&showHidden=``."""


class V4AdminUserDataExportView(_V4AdminMixin, AdminDumpUserDataView):
    """``POST /api/v4/admin/user-data/export``."""


class V4AdminUserDataImportView(_V4AdminMixin, AdminRestoreUserDataView):
    """``POST /api/v4/admin/user-data/import``."""
