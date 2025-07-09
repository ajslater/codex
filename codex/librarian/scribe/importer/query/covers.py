"""Query Missing Custom Covers."""

from codex.librarian.scribe.importer.const import (
    CREATE_COVERS,
    UPDATE_COVERS,
)
from codex.librarian.scribe.importer.create import CreateForeignKeysImporter
from codex.librarian.scribe.importer.statii.create import (
    ImporterCreateCoversStatus,
    ImporterUpdateCoversStatus,
)
from codex.librarian.scribe.importer.statii.query import (
    ImporterQueryMissingCoversStatus,
)
from codex.models.paths import CustomCover


class QueryCustomCoversImporter(CreateForeignKeysImporter):
    """Query Missing Custom Covers."""

    def query_missing_custom_covers(self):
        """Identify update & create covers."""
        cover_paths = self.task.covers_created | self.task.covers_modified
        num_cover_paths = len(cover_paths)
        status = ImporterQueryMissingCoversStatus(None, num_cover_paths)
        if not num_cover_paths:
            self.status_controller.finish(status)
            return
        self.log.debug(f"Querying {num_cover_paths} custom cover_paths")
        self.status_controller.start(status)

        update_covers_qs = CustomCover.objects.filter(
            library=self.library, path__in=cover_paths
        )
        self.metadata[UPDATE_COVERS] = update_covers_qs
        update_cover_paths = frozenset(update_covers_qs.values_list("path", flat=True))
        update_count = len(update_cover_paths)
        update_status = ImporterUpdateCoversStatus(0, update_count)
        self.status_controller.update(update_status)

        create_cover_paths = cover_paths - update_cover_paths
        self.metadata[CREATE_COVERS] = create_cover_paths
        create_count = len(create_cover_paths)
        create_status = ImporterCreateCoversStatus(0, create_count)
        self.status_controller.update(create_status)

        self.task.covers_created = self.task.covers_modified = frozenset()

        count = create_count + update_count
        if count:
            self.log.debug(
                f"Discovered {update_count} custom covers to update and {create_count} to create."
            )
        self.status_controller.finish(status)
        return
