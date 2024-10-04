"""Librarian Status View."""

from types import MappingProxyType
from typing import TYPE_CHECKING

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.librarian.covers.tasks import (
    CoverCreateAllTask,
    CoverRemoveAllTask,
    CoverRemoveOrphansTask,
)
from codex.librarian.importer.tasks import (
    AdoptOrphanFoldersTask,
    UpdateGroupsTask,
)
from codex.librarian.janitor.tasks import (
    ForceUpdateAllFailedImportsTask,
    JanitorBackupTask,
    JanitorCleanCoversTask,
    JanitorCleanFKsTask,
    JanitorCleanupBookmarksTask,
    JanitorCleanupSessionsTask,
    JanitorClearStatusTask,
    JanitorForeignKeyCheck,
    JanitorFTSIntegrityCheck,
    JanitorFTSRebuildTask,
    JanitorIntegrityCheck,
    JanitorLatestVersionTask,
    JanitorNightlyTask,
    JanitorRestartTask,
    JanitorShutdownTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK, LIBRARY_CHANGED_TASK
from codex.librarian.search.tasks import (
    SearchIndexAbortTask,
    SearchIndexClearTask,
    SearchIndexOptimizeTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.watchdog.tasks import (
    WatchdogPollLibrariesTask,
    WatchdogSyncTask,
)
from codex.logger.logging import get_logger
from codex.models import LibrarianStatus
from codex.serializers.admin.tasks import AdminLibrarianTaskSerializer
from codex.serializers.mixins import OKSerializer
from codex.serializers.models.admin import LibrarianStatusSerializer
from codex.views.admin.auth import AdminAPIView, AdminReadOnlyModelViewSet
from codex.views.const import EPOCH_START

if TYPE_CHECKING:
    from collections.abc import Mapping

LOG = get_logger(__name__)

_TASK_MAP = MappingProxyType(
    {
        "purge_comic_covers": CoverRemoveAllTask(),
        "create_all_comic_covers": CoverCreateAllTask(),
        "search_index_update": SearchIndexUpdateTask(False),
        "search_index_rebuild": SearchIndexUpdateTask(True),
        "search_index_remove_stale": SearchIndexRemoveStaleTask(),
        "search_index_abort": SearchIndexAbortTask(),
        "search_index_optimize": SearchIndexOptimizeTask(True),
        "search_index_clear": SearchIndexClearTask(),
        "db_vacuum": JanitorVacuumTask(),
        "db_backup": JanitorBackupTask(),
        "db_foreign_key_check": JanitorForeignKeyCheck(),
        "db_integrity_check": JanitorIntegrityCheck(),
        "db_fts_integrity_check": JanitorFTSIntegrityCheck(),
        "db_fts_rebuild": JanitorFTSRebuildTask(),
        "watchdog_sync": WatchdogSyncTask(),
        "codex_latest_version": JanitorLatestVersionTask(True),
        "codex_update": JanitorUpdateTask(False),
        "codex_shutdown": JanitorShutdownTask(),
        "codex_restart": JanitorRestartTask(),
        "notify_library_changed": LIBRARY_CHANGED_TASK,
        "notify_librarian_status": LIBRARIAN_STATUS_TASK,
        "cleanup_fks": JanitorCleanFKsTask(),
        "cleanup_db_custom_covers": JanitorCleanCoversTask(),
        "cleanup_sessions": JanitorCleanupSessionsTask(),
        "cleanup_bookmarks": JanitorCleanupBookmarksTask(),
        "cleanup_covers": CoverRemoveOrphansTask(),
        "librarian_clear_status": JanitorClearStatusTask(),
        "force_update_all_failed_imports": ForceUpdateAllFailedImportsTask(),
        "poll": WatchdogPollLibrariesTask(frozenset(), False),
        "poll_force": WatchdogPollLibrariesTask(frozenset(), True),
        "janitor_nightly": JanitorNightlyTask(),
        "force_update_groups": UpdateGroupsTask(start_time=EPOCH_START),
        "adopt_folders": AdoptOrphanFoldersTask(),
    }
)


class AdminLibrarianStatusViewSet(AdminReadOnlyModelViewSet):
    """Librarian Task Statuses."""

    queryset = LibrarianStatus.objects.filter(active__isnull=False).order_by(
        "active", "pk"
    )
    serializer_class = LibrarianStatusSerializer


class AdminLibrarianTaskView(AdminAPIView):
    """Queue Librarian Jobs."""

    input_serializer_class = AdminLibrarianTaskSerializer
    serializer_class = OKSerializer

    @classmethod
    def _get_task(cls, name, pk):
        """Stuff library ids into tasks."""
        task = _TASK_MAP.get(name)
        if pk and isinstance(
            task, WatchdogPollLibrariesTask | WatchdogPollLibrariesTask
        ):
            task.library_ids = frozenset({pk})
        return task

    @extend_schema(request=input_serializer_class)
    def post(self, *_args, **_kwargs):
        """Download a comic archive."""
        # DRF does not populate POST correctly, only data
        data = self.request.data  # type:ignore
        serializer = self.input_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data: Mapping = serializer.validated_data  # type: ignore
        task_name = validated_data.get("task")
        pk = validated_data.get("library_id")
        task = self._get_task(task_name, pk)
        if task:
            LIBRARIAN_QUEUE.put(task)
        else:
            reason = f"Unknown admin library task_name: {task_name}"
            LOG.warning(reason)
            raise ValueError(reason)

        serializer = self.serializer_class()
        return Response(serializer.data)
