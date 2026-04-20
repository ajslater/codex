"""Delete comics methods."""

from codex.librarian.scribe.importer.const import ALL_COMIC_GROUP_FIELD_NAMES
from codex.librarian.scribe.importer.delete.covers import DeletedCoversImporter
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveComicsStatus
from codex.models import Comic, Folder, StoryArc
from codex.settings import (
    IMPORTER_DELETE_MAX_CHUNK_SIZE,
    IMPORTER_LINK_FK_BATCH_SIZE,
)


class DeletedComicsImporter(DeletedCoversImporter):
    """Delete comics methods."""

    @staticmethod
    def _init_deleted_comic_groups() -> dict:
        """Init deleted_comic_groups, used later even if no deletes."""
        deleted_comic_groups = {}
        for field_name in ALL_COMIC_GROUP_FIELD_NAMES:
            if field_name == "story_arc_numbers":
                related_model = StoryArc
            else:
                related_model = Comic._meta.get_field(field_name).related_model
            deleted_comic_groups[related_model] = set()
        return deleted_comic_groups

    @staticmethod
    def _populate_deleted_comic_group(deleted_comic_groups, comic) -> None:
        for field_name in ALL_COMIC_GROUP_FIELD_NAMES:
            if field_name == "story_arc_numbers":
                for san in comic.story_arc_numbers.select_related("story_arc").only(
                    "story_arc"
                ):
                    deleted_comic_groups[StoryArc].add(san.story_arc.pk)
            elif field_name == "folders":
                for folder in comic.folders.only("pk"):
                    deleted_comic_groups[Folder].add(folder.pk)
            else:
                related_model = comic._meta.get_field(field_name).related_model
                related_id = getattr(comic, field_name).pk
                deleted_comic_groups[related_model].add(related_id)

    @classmethod
    def _populate_deleted_comic_groups(cls, delete_qs, deleted_comic_groups) -> None:
        """Populate changed groups for cover timestamp updater."""
        comics_deleted_qs = delete_qs.only(
            *ALL_COMIC_GROUP_FIELD_NAMES
        ).prefetch_related("story_arc_numbers__story_arc")
        for comic in comics_deleted_qs.iterator(
            chunk_size=IMPORTER_DELETE_MAX_CHUNK_SIZE
        ):
            cls._populate_deleted_comic_group(deleted_comic_groups, comic)

    def bulk_comics_deleted(self, **kwargs) -> tuple[int, dict]:
        """Bulk delete comics found missing from the filesystem."""
        count = 0
        deleted_comic_groups = self._init_deleted_comic_groups()
        status = ImporterRemoveComicsStatus(0, len(self.task.files_deleted))
        try:
            if not self.task.files_deleted:
                return count, deleted_comic_groups
            self.status_controller.start(status)
            # Batch path__in to stay under SQLite's variable limit.
            paths = tuple(self.task.files_deleted)
            self.task.files_deleted = frozenset()
            delete_comic_pks: set[int] = set()
            for start in range(0, len(paths), IMPORTER_LINK_FK_BATCH_SIZE):
                if self.abort_event.is_set():
                    break
                batch_paths = paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
                delete_qs = Comic.objects.filter(
                    library=self.library, path__in=batch_paths
                )
                self._populate_deleted_comic_groups(delete_qs, deleted_comic_groups)
                delete_comic_pks.update(delete_qs.values_list("pk", flat=True))
                delete_qs.delete()

            count = len(delete_comic_pks)
            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return count, deleted_comic_groups
