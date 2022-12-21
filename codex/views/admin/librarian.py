"""Librarian Status View."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from codex.librarian.covers.tasks import CoverRemoveAllTask, CoverRemoveOrphansTask
from codex.librarian.janitor.tasks import (
    JanitorBackupTask,
    JanitorCleanFKsTask,
    JanitorCleanSearchTask,
    JanitorClearStatusTask,
    JanitorRestartTask,
    JanitorShutdownTask,
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
from codex.serializers.admin import AdminLibrarianTaskSerializer
from codex.serializers.mixins import OKSerializer
from codex.serializers.models import LibrarianStatusSerializer
from codex.settings.logging import get_logger


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

    @staticmethod
    def _get_all_library_pks():
        queryset = Library.objects.all()
        return frozenset(queryset.values_list("pk", flat=True))

    @classmethod
    def _poll_libraries(cls, force, pk=None):
        """Queue a poll task for the library."""
        if pk:
            pks = frozenset((pk,))
        else:
            pks = cls._get_all_library_pks()
        return WatchdogPollLibrariesTask(pks, force)

    @extend_schema(request=input_serializer_class)
    def post(self, request, *args, **kwargs):
        """Download a comic archive."""
        serializer = self.input_serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        task_name = serializer.validated_data.get("task")
        task = None
        if task_name == "poll":
            pk = serializer.validated_data.get("library_id")
            task = self._poll_libraries(False, pk)
        elif task_name == "poll_force":
            pk = serializer.validated_data.get("library_id")
            task = self._poll_libraries(True, pk)
        elif task_name == "purge_comic_covers":
            task = CoverRemoveAllTask()
        elif task_name == "search_index_update":
            task = SearchIndexJanitorUpdateTask(False)
        elif task_name == "search_index_rebuild":
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
        elif task_name == "codex_shutdown":
            task = JanitorShutdownTask()
        elif task_name == "notify_library_changed":
            task = LIBRARY_CHANGED_TASK
        elif task_name == "cleanup_queries":
            task = JanitorCleanSearchTask()
        elif task_name == "cleanup_fks":
            task = JanitorCleanFKsTask()
        elif task_name == "cleanup_covers":
            task = CoverRemoveOrphansTask()
        elif task_name == "librarian_clear_status":
            task = JanitorClearStatusTask()

        if task:
            LIBRARIAN_QUEUE.put(task)
        else:
            LOG.warning(f"Unknown admin library task_name: {task_name}")
            raise ValueError(f"Unknown admin library task_name: {task_name}")

        serializer = self.serializer_class()
        return Response(serializer.data)
