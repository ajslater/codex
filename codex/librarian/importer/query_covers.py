"""Query Missing Custom Covers."""

from codex.librarian.importer.const import (
    COVERS_CREATE,
    COVERS_UPDATE,
)
from codex.librarian.importer.create_fks import CreateForeignKeysImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.logger.logging import get_logger
from codex.models.paths import CustomCover
from codex.status import Status

LOG = get_logger(__name__)


class QueryCustomCoversImporter(CreateForeignKeysImporter):
    """Query Missing Custom Covers."""

    def query_missing_custom_covers(self):
        """Identify update & create covers."""
        cover_paths = self.task.covers_created | self.task.covers_modified
        num_cover_paths = len(cover_paths)
        if not num_cover_paths:
            return
        self.log.debug(f"Querying {num_cover_paths} custom cover_paths")
        status = Status(ImportStatusTypes.QUERY_MISSING_COVERS, None, num_cover_paths)
        self.status_controller.start(status)

        update_covers_qs = CustomCover.objects.filter(
            library=self.library, path__in=cover_paths
        )
        self.metadata[COVERS_UPDATE] = update_covers_qs
        update_cover_paths = frozenset(update_covers_qs.values_list("path", flat=True))
        update_count = len(update_cover_paths)
        update_status = Status(ImportStatusTypes.COVERS_MODIFIED, 0, update_count)
        self.status_controller.update(update_status, notify=False)

        create_cover_paths = cover_paths - update_cover_paths
        self.metadata[COVERS_CREATE] = create_cover_paths
        create_count = len(create_cover_paths)
        create_status = Status(ImportStatusTypes.COVERS_CREATED, 0, create_count)
        self.status_controller.update(create_status, notify=False)

        self.task.covers_created = self.task.covers_modified = frozenset()

        count = create_count + update_count
        if count:
            self.log.debug(
                f"Discovered {update_count} custom covers to update and {create_count} to create."
            )
        self.status_controller.finish(status)
        return
