"""Admin Library Views."""
from pathlib import Path

from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, DelayedTasks
from codex.librarian.watchdog.tasks import WatchdogPollLibrariesTask, WatchdogSyncTask
from codex.models import FailedImport, Folder, Library
from codex.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.serializers.admin import (
    AdminFolderListSerializer,
    AdminFolderSerializer,
    FailedImportSerializer,
    LibrarySerializer,
)
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


class AdminLibraryViewSet(ModelViewSet):
    """Admin Library Viewset."""

    permission_classes = [IsAdminUser]
    queryset = Library.objects.prefetch_related("groups").defer(
        "update_in_progress", "created_at", "updated_at"
    )
    serializer_class = LibrarySerializer

    WATCHDOG_SYNC_FIELDS = set(("events", "poll", "pollEvery"))

    def _create_library_folder(self, library):
        folder = Folder(
            library=library, path=library.path, name=Path(library.path).name
        )
        folder.save()

    @staticmethod
    def _sync_watchdog():
        tasks = (WatchdogSyncTask(),)
        task = DelayedTasks(2, tasks)
        LIBRARIAN_QUEUE.put(task)

    @staticmethod
    def _on_change():
        cache.clear()
        task = LIBRARY_CHANGED_TASK
        LIBRARIAN_QUEUE.put(task)

    @staticmethod
    def _poll(pk, force):
        task = WatchdogPollLibrariesTask(frozenset((pk,)), force)
        LIBRARIAN_QUEUE.put(task)

    def perform_update(self, serializer):
        """Perform update an run hooks."""
        validated_keys = set(serializer.validated_data.keys())
        super().perform_update(serializer)
        if "groupSet" in validated_keys:
            self._on_change()
        if validated_keys.intersection(self.WATCHDOG_SYNC_FIELDS):
            self._sync_watchdog()
        pk = self.kwargs.get("pk")
        self._poll(pk, False)

    def perform_create(self, serializer):
        """Perform create and run hooks."""
        super().perform_create(serializer)
        library = Library.objects.only("pk", "path").get(
            path=serializer.validated_data["path"]
        )
        self._create_library_folder(library)
        self._sync_watchdog()
        self._poll(library.pk, False)

    def perform_destroy(self, instance):
        """Perform destroy and run hooks."""
        super().perform_destroy(instance)
        self._sync_watchdog()
        self._on_change()


class AdminFailedImportViewSet(ModelViewSet):
    """Admin FailedImport Viewset."""

    permission_classes = [IsAdminUser]
    queryset = FailedImport.objects.defer("updated_at")
    serializer_class = FailedImportSerializer


class AdminFolderListView(GenericAPIView):
    """List server directories."""

    permission_classes = [IsAdminUser]
    serializer_class = AdminFolderListSerializer
    input_serializer_class = AdminFolderSerializer

    def get(self, request, *args, **kwargs):
        """Get subdirectories for a path."""
        try:
            serializer = self.input_serializer_class(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            path = serializer.validated_data.get("path", Path("."))
            show_hidden = serializer.validated_data.get("show_hidden", False)
            root_path = path.resolve()

            dirs = []
            if root_path.parent != root_path:
                dirs += [".."]
            subdirs = []
            for fn in root_path.iterdir():
                if fn.is_dir() and (show_hidden or not fn.name.startswith(".")):
                    subdirs.append(fn.name)
            dirs += sorted(subdirs)

            data = {"root_folder": str(root_path), "folders": dirs}
            serializer = self.get_serializer(data)
            return Response(serializer.data)
        except Exception as exc:
            raise ValidationError("Server Error") from exc
