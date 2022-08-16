"""Queue Libraian Jobs."""
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from codex.librarian.covers.tasks import (
    CoverCreateForLibrariesTask,
    CoverRemoveAllTask,
    CoverRemoveOrphansTask,
)
from codex.librarian.janitor.tasks import (
    JanitorBackupTask,
    JanitorCleanFKsTask,
    JanitorCleanSearchTask,
    JanitorClearStatusTask,
    JanitorRestartTask,
    JanitorUpdateTask,
    JanitorVacuumTask,
)
from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.search.tasks import (
    SearchIndexJanitorUpdateTask,
    SearchIndexRebuildIfDBChangedTask,
)
from codex.librarian.watchdog.tasks import WatchdogPollLibrariesTask, WatchdogSyncTask
from codex.models import LibrarianStatus, Library
from codex.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.serializers.admin import QueueJobSerializer
from codex.serializers.models import LibrarianStatusSerializer
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class QueueLibrarianJobs(APIView):
    """Queue Librarian Jobs."""

    permission_classes = [IsAdminUser]

    @staticmethod
    def _get_all_library_pks():
        queryset = Library.objects.all()
        return frozenset(queryset.values_list("pk", flat=True))

    @classmethod
    def _poll_all_libraries(cls, force):
        """Queue a poll task for the library."""
        pks = cls._get_all_library_pks()
        return WatchdogPollLibrariesTask(pks, force)

    def post(self, request, *args, **kwargs):
        """Download a comic archive."""
        serializer = QueueJobSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        task_name = serializer.validated_data.get("task")
        task = None
        if task_name == "poll":
            task = self._poll_all_libraries(False)
        elif task_name == "poll_force":
            task = self._poll_all_libraries(True)
        elif task_name == "clean_queries":
            task = JanitorCleanSearchTask()
        elif task_name == "create_missing_covers":
            library_pks = self._get_all_library_pks()
            task = CoverCreateForLibrariesTask(library_pks)
        elif task_name == "purge_comic_covers":
            task = CoverRemoveAllTask()
        elif task_name == "update_index":
            task = SearchIndexJanitorUpdateTask(False)
        elif task_name == "rebuild_index":
            task = SearchIndexJanitorUpdateTask(True)
        elif task_name == "db_vacuum":
            task = JanitorVacuumTask()
        elif task_name == "db_backup":
            task = JanitorBackupTask()
        elif task_name == "db_search_sync":
            task = SearchIndexRebuildIfDBChangedTask()
        elif task_name == "watchdog_sync":
            task = WatchdogSyncTask()
        elif task_name == "codex_update":
            task = JanitorUpdateTask(False)
        elif task_name == "codex_restart":
            task = JanitorRestartTask()
        elif task_name == "notify_all":
            task = LIBRARY_CHANGED_TASK
        elif task_name == "cleanup_fks":
            task = JanitorCleanFKsTask()
        elif task_name == "cleanup_covers":
            task = CoverRemoveOrphansTask()
        elif task_name == "librarian_clear_status":
            task = JanitorClearStatusTask()

        if task:
            LIBRARIAN_QUEUE.put(task)
            status = HTTP_200_OK
        else:
            LOG.warning(f"Unknown admin library task_name: {task_name}")
            status = HTTP_400_BAD_REQUEST

        return Response({}, status=status)


class LibrarianStatusViewSet(ReadOnlyModelViewSet):
    """Librarian Task Statuses."""

    permission_classes = [IsAdminUser]
    queryset = LibrarianStatus.objects.filter(active__isnull=False).order_by(
        "active", "pk"
    )
    serializer_class = LibrarianStatusSerializer
