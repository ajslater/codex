"""Librarian Status View."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from codex.librarian.covers.tasks import CoverRemoveAllTask, CoverRemoveOrphansTask
from codex.librarian.janitor.tasks import (
    ForceUpdateAllFailedImportsTask,
    JanitorBackupTask,
    JanitorCleanFKsTask,
    JanitorCleanupSessionsTask,
    JanitorClearStatusTask,
    JanitorNightlyTask,
    JanitorShutdownTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARIAN_STATUS_TASK, LIBRARY_CHANGED_TASK
from codex.librarian.search.tasks import (
    SearchIndexAbortTask,
    SearchIndexMergeTask,
    SearchIndexRebuildIfDBChangedTask,
    SearchIndexRemoveStaleTask,
    SearchIndexUpdateTask,
)
from codex.librarian.watchdog.tasks import WatchdogPollLibrariesTask, WatchdogSyncTask
from codex.logger.logging import get_logger
from codex.models import LibrarianStatus
from codex.serializers.admin import AdminLibrarianTaskSerializer
from codex.serializers.mixins import OKSerializer
from codex.serializers.models import LibrarianStatusSerializer

LOG = get_logger(__name__)


class AdminLibrarianStatusViewSet(ReadOnlyModelViewSet):
    """Librarian Task Statuses."""

    permission_classes = [IsAdminUser]
    queryset = LibrarianStatus.objects.filter(active__isnull=False).order_by(
        "active", "pk"
    )
    serializer_class = LibrarianStatusSerializer


class AdminLibrarianTaskView(APIView):
    """Queue Librarian Jobs."""

    permission_classes = [IsAdminUser]
    input_serializer_class = AdminLibrarianTaskSerializer
    serializer_class = OKSerializer

    _TASK_MAP = {
        "purge_comic_covers": CoverRemoveAllTask(),
        "search_index_update": SearchIndexUpdateTask(False),
        "search_index_rebuild": SearchIndexUpdateTask(True),
        "search_index_remove_stale": SearchIndexRemoveStaleTask(),
        "search_index_merge_small": SearchIndexMergeTask(
            False,
        ),
        "search_index_abort": SearchIndexAbortTask(),
        "search_index_optimize": SearchIndexMergeTask(True),
        "db_vacuum": JanitorVacuumTask(),
        "db_backup": JanitorBackupTask(),
        "db_search_sync": SearchIndexRebuildIfDBChangedTask(),
        "watchdog_sync": WatchdogSyncTask(),
        "codex_update": JanitorUpdateTask(False),
        "codex_shutdown": JanitorShutdownTask(),
        "notify_library_changed": LIBRARY_CHANGED_TASK,
        "notify_librarian_status": LIBRARIAN_STATUS_TASK,
        "cleanup_fks": JanitorCleanFKsTask(),
        "cleanup_sessions": JanitorCleanupSessionsTask(),
        "cleanup_covers": CoverRemoveOrphansTask(),
        "librarian_clear_status": JanitorClearStatusTask(),
        "force_update_all_failed_imports": ForceUpdateAllFailedImportsTask(),
        "poll": WatchdogPollLibrariesTask(frozenset(), False),
        "poll_force": WatchdogPollLibrariesTask(frozenset(), True),
        "janitor_nightly": JanitorNightlyTask(),
    }

    @extend_schema(request=input_serializer_class)
    def post(self, *args, **kwargs):
        """Download a comic archive."""
        serializer = self.input_serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        task_name = serializer.validated_data.get("task")
        task = self._TASK_MAP.get(task_name)
        if task:
            LIBRARIAN_QUEUE.put(task)
        else:
            reason = f"Unknown admin library task_name: {task_name}"
            LOG.warning(reason)
            raise ValueError(reason)

        serializer = self.serializer_class()
        return Response(serializer.data)
