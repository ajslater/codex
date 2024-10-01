"""Admin Library Views."""

from pathlib import Path
from time import time

from django.core.cache import cache
from django.db.utils import NotSupportedError
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.librarian.tasks import DelayedTasks
from codex.librarian.watchdog.tasks import (
    WatchdogPollLibrariesTask,
    WatchdogSyncTask,
)
from codex.logger.logging import get_logger
from codex.models import FailedImport, Folder, Library
from codex.serializers.admin.libraries import (
    AdminFolderListSerializer,
    AdminFolderSerializer,
    FailedImportSerializer,
    LibrarySerializer,
)
from codex.views.admin.auth import AdminGenericAPIView, AdminModelViewSet

LOG = get_logger(__name__)


class AdminLibraryViewSet(AdminModelViewSet):
    """Admin Library Viewset."""

    _WATCHDOG_SYNC_FIELDS = frozenset({"events", "poll", "pollEvery"})

    queryset = Library.objects.prefetch_related("groups").defer(
        "update_in_progress", "created_at", "updated_at"
    )
    serializer_class = LibrarySerializer

    @classmethod
    def _sync_watchdog(cls, validated_keys=None):
        if validated_keys is None or validated_keys.intersection(
            cls._WATCHDOG_SYNC_FIELDS
        ):
            task = DelayedTasks(time() + 2, (WatchdogSyncTask(),))
            LIBRARIAN_QUEUE.put(task)

    @staticmethod
    def _on_change():
        cache.clear()
        task = LIBRARY_CHANGED_TASK
        LIBRARIAN_QUEUE.put(task)

    def _create_library_folder(self, library):
        folder = Folder(
            library=library, path=library.path, name=Path(library.path).name
        )
        folder.save()

    @staticmethod
    def _poll(pk, force):
        task = WatchdogPollLibrariesTask(frozenset({pk}), force)
        LIBRARIAN_QUEUE.put(task)

    def perform_create(self, serializer):
        """Perform create and run hooks."""
        super().perform_create(serializer)
        if serializer.validated_data.get("covers_only"):
            raise NotSupportedError
        library = Library.objects.only("pk", "path").get(
            path=serializer.validated_data["path"]
        )
        self._create_library_folder(library)
        self._sync_watchdog()
        self._poll(library.pk, False)

    def perform_update(self, serializer):
        """Perform update an run hooks."""
        validated_keys = frozenset(serializer.validated_data.keys())
        pk = self.kwargs["pk"]
        library = Library.objects.get(pk=pk)
        if library.covers_only and serializer.validated_data.get("path"):
            raise NotSupportedError
        super().perform_update(serializer)
        if "groupSet" in validated_keys:
            self._on_change()
        self._sync_watchdog(validated_keys)
        self._poll(pk, False)

    def perform_destroy(self, instance):
        """Perform destroy and run hooks."""
        if instance.covers_only:
            raise NotSupportedError
        super().perform_destroy(instance)
        self._sync_watchdog()
        self._on_change()


class AdminFailedImportViewSet(AdminModelViewSet):
    """Admin FailedImport Viewset."""

    queryset = FailedImport.objects.defer("updated_at")
    serializer_class = FailedImportSerializer


class AdminFolderListView(AdminGenericAPIView):
    """List server directories."""

    serializer_class = AdminFolderListSerializer
    input_serializer_class = AdminFolderSerializer

    @staticmethod
    def _get_dirs(root_path, show_hidden):
        """Get dirs list."""
        dirs = []
        if root_path.parent != root_path:
            dirs += [".."]
        subdirs = []
        for subpath in root_path.iterdir():
            if subpath.name.startswith(".") and not show_hidden:
                continue
            if subpath.resolve().is_dir():
                subdirs.append(subpath.name)
        dirs += sorted(subdirs)
        return tuple(dirs)

    @extend_schema(request=input_serializer_class)
    def get(self, *_args, **_kwargs):
        """Get subdirectories for a path."""
        try:
            serializer = self.input_serializer_class(data=self.request.GET)
            serializer.is_valid(raise_exception=True)
            root_path = Path(serializer.validated_data.get("path", ".")).resolve()  # type: ignore
            show_hidden = serializer.validated_data.get("show_hidden", False)  # type: ignore

            dirs = self._get_dirs(root_path, show_hidden)

            data = {"root_folder": str(root_path), "folders": dirs}
            serializer = self.get_serializer(data)
        except ValidationError:
            raise
        except Exception as exc:
            LOG.exception("get admin folder list view")
            reason = "Server Error"
            raise ValidationError(reason) from exc
        else:
            return Response(serializer.data)
