"""Admin Library Views."""

import os
from pathlib import Path
from typing import override

from django.core.cache import cache
from django.db.models import Case, OuterRef, Subquery, When
from django.db.models.aggregates import Count
from django.db.models.expressions import Value
from django.db.models.functions import Coalesce
from django.db.utils import NotSupportedError
from drf_spectacular.utils import extend_schema
from loguru import logger
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from codex.librarian.fs.poller.tasks import FSPollLibrariesTask
from codex.librarian.fs.watcher.tasks import FSWatcherRestartTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.models import Comic, CustomCover, FailedImport, Folder, Library
from codex.serializers.admin.libraries import (
    AdminFolderListSerializer,
    AdminFolderSerializer,
    FailedImportSerializer,
    LibrarySerializer,
)
from codex.views.admin.auth import AdminGenericAPIView, AdminModelViewSet

# Per-Library count subqueries. Each is a correlated index-only count
# against the related table's ``library_id`` index — no JOIN, no
# DISTINCT. Replaces the prior ``Count("comic", distinct=True)`` /
# ``Count("failedimport", distinct=True)`` annotations whose JOIN
# materialized the Cartesian product before DISTINCT collapsed it.
_CUSTOM_COVER_COUNT = Coalesce(
    Subquery(
        CustomCover.objects.exclude(group="f")
        .values("group")  # A dummy group-by to allow the annotation
        .annotate(cnt=Count("pk"))
        .values("cnt")[:1]
    ),
    Value(0),
)
_COMIC_COUNT = Coalesce(
    Subquery(
        Comic.objects.filter(library=OuterRef("pk"))
        .values("library")
        .annotate(cnt=Count("pk"))
        .values("cnt")[:1]
    ),
    Value(0),
)
_FAILED_COUNT = Coalesce(
    Subquery(
        FailedImport.objects.filter(library=OuterRef("pk"))
        .values("library")
        .annotate(cnt=Count("pk"))
        .values("cnt")[:1]
    ),
    Value(0),
)


class AdminLibraryViewSet(AdminModelViewSet):
    """Admin Library Viewset."""

    _WATCHER_SYNC_FIELDS = frozenset({"events", "poll", "pollEvery"})
    serializer_class = LibrarySerializer

    queryset = (
        Library.objects.prefetch_related("groups")
        .annotate(
            comic_count=Case(
                # covers_only libraries borrow the CustomCover count;
                # everything else uses a per-library correlated count.
                When(covers_only=True, then=_CUSTOM_COVER_COUNT),
                default=_COMIC_COUNT,
            ),
            failed_count=_FAILED_COUNT,
        )
        .defer("update_in_progress", "created_at", "updated_at")
    )

    @classmethod
    def _sync_watcher(cls, validated_keys=None) -> None:
        if validated_keys is None or validated_keys.intersection(
            cls._WATCHER_SYNC_FIELDS
        ):
            task = FSWatcherRestartTask()
            LIBRARIAN_QUEUE.put(task)

    @staticmethod
    def _on_change() -> None:
        cache.clear()
        task = LIBRARY_CHANGED_TASK
        LIBRARIAN_QUEUE.put(task)

    @staticmethod
    def _create_library_folder(library) -> None:
        folder = Folder(
            library=library, path=library.path, name=Path(library.path).name
        )
        folder.save()

    @staticmethod
    def _poll(pk, force) -> None:
        task = FSPollLibrariesTask(frozenset({pk}), force)
        LIBRARIAN_QUEUE.put(task)

    @override
    def perform_create(self, serializer) -> None:
        """Perform create and run hooks."""
        super().perform_create(serializer)
        if serializer.validated_data.get("covers_only"):
            raise NotSupportedError
        library = Library.objects.only("pk", "path").get(
            path=serializer.validated_data["path"]
        )
        self._create_library_folder(library)
        self._sync_watcher()
        self._poll(library.pk, force=False)

    @override
    def perform_update(self, serializer) -> None:
        """Perform update an run hooks."""
        validated_keys = frozenset(serializer.validated_data.keys())
        pk = self.kwargs["pk"]
        library = Library.objects.get(pk=pk)
        if library.covers_only and serializer.validated_data.get("path"):
            raise NotSupportedError
        super().perform_update(serializer)
        if "groupSet" in validated_keys:
            self._on_change()
        self._sync_watcher(validated_keys)
        self._poll(pk, force=False)

    @override
    def perform_destroy(self, instance) -> None:
        """Perform destroy and run hooks."""
        if instance.covers_only:
            raise NotSupportedError
        super().perform_destroy(instance)
        self._sync_watcher()
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
    def _get_dirs(root_path, show_hidden) -> tuple[str, ...]:
        """
        Get dirs list.

        Uses :func:`os.scandir` so each entry's directory check is a
        single ``stat`` instead of the prior ``Path.iterdir()`` plus
        ``Path.resolve().is_dir()`` (which chains a full readlink walk
        before stat-ing). Broken symlinks are skipped silently.
        """
        dirs: list[str] = []
        if root_path.parent != root_path:
            dirs.append("..")
        subdirs: list[str] = []
        with os.scandir(root_path) as it:
            for entry in it:
                if entry.name.startswith(".") and not show_hidden:
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=True)
                except OSError:
                    # Broken symlink or permission denied — skip silently.
                    continue
                if is_dir:
                    subdirs.append(entry.name)
        dirs.extend(sorted(subdirs))
        return tuple(dirs)

    @extend_schema(request=input_serializer_class)
    def get(self, *_args, **_kwargs) -> Response:
        """Get subdirectories for a path."""
        try:
            serializer = self.input_serializer_class(data=self.request.GET)
            serializer.is_valid(raise_exception=True)
            root_path = Path(serializer.validated_data.get("path", ".")).resolve()
            show_hidden = serializer.validated_data.get("show_hidden", False)

            dirs = self._get_dirs(root_path, show_hidden)

            data = {"root_folder": str(root_path), "folders": dirs}
            serializer = self.get_serializer(data)
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception("get admin folder list view")
            reason = "Server Error"
            raise ValidationError(reason) from exc
        else:
            return Response(serializer.data)
