"""Queue Libraian Jobs."""
from logging import getLogger

from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from codex.librarian.queue_mp import (
    LIBRARIAN_QUEUE,
    BackupTask,
    BroadcastNotifierTask,
    CleanSearchTask,
    CleanupDatabaseTask,
    CreateComicCoversLibrariesTask,
    PollLibrariesTask,
    RebuildSearchIndexIfDBChangedTask,
    RestartTask,
    UpdateSearchIndexTask,
    UpdateTask,
    VacuumTask,
    WatchdogSyncTask,
)
from codex.models import Library
from codex.serializers.admin import QueueJobSerializer


LOG = getLogger(__name__)


class QueueLibrarianJobs(APIView):
    """Queue Librarian Jobs."""

    permission_classes = [IsAdminUser]

    @staticmethod
    def _get_all_library_pks():
        queryset = Library.objects.all()
        return set(queryset.values_list("pk", flat=True))

    @classmethod
    def _poll_all_libraries(cls, force):
        """Queue a poll task for the library."""
        pks = cls._get_all_library_pks()
        return PollLibrariesTask(pks, force)

    @classmethod
    def _regen_all_comic_covers(cls):
        """Regenerate all covers."""
        pks = cls._get_all_library_pks()
        return CreateComicCoversLibrariesTask(pks)

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
            task = CleanSearchTask()
        elif task_name == "create_comic_covers":
            task = self._regen_all_comic_covers()
        elif task_name == "update_index":
            task = UpdateSearchIndexTask(False)
        elif task_name == "rebuild_index":
            task = UpdateSearchIndexTask(True)
        elif task_name == "db_cleanup":
            task = CleanupDatabaseTask()
        elif task_name == "db_vacuum":
            task = VacuumTask()
        elif task_name == "db_backup":
            task = BackupTask()
        elif task_name == "db_search_sync":
            task = RebuildSearchIndexIfDBChangedTask()
        elif task_name == "watchdog_sync":
            task = WatchdogSyncTask()
        elif task_name == "codex_update":
            task = UpdateTask(False)
        elif task_name == "codex_restart":
            task = RestartTask()
        elif task_name == "notify_all":
            task = BroadcastNotifierTask("LIBRARY_CHANGED")

        if task:
            LIBRARIAN_QUEUE.put(task)
            status = HTTP_200_OK
        else:
            LOG.warning(f"Unknown admin library task_name: {task_name}")
            status = HTTP_400_BAD_REQUEST

        return Response({}, status=status)
