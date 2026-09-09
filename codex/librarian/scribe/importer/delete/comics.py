"""Delete comics methods."""

from codex.librarian.scribe.importer.const import (
    ALL_COMIC_COLLECTION_FIELD_NAMES,
    DIRECT_M2M_COLLECTION_FIELD_NAMES,
)
from codex.librarian.scribe.importer.delete.covers import DeletedCoversImporter
from codex.librarian.scribe.importer.delete.existence import confirm_deleted
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveComicsStatus
from codex.models import Comic, StoryArc
from codex.settings import (
    IMPORTER_DELETE_MAX_CHUNK_SIZE,
    IMPORTER_LINK_FK_BATCH_SIZE,
)

# A delete this large, and this much of the library, reads like a vanished
# mount rather than a user tidying up. The floor keeps small libraries from
# tripping it whenever a couple of comics are removed.
_MASS_DELETE_FLOOR = 50
_MASS_DELETE_FRACTION = 0.5


class DeletedComicsImporter(DeletedCoversImporter):
    """Delete comics methods."""

    @staticmethod
    def _init_deleted_comic_collections() -> dict:
        """Init deleted_comic_collections, used later even if no deletes."""
        deleted_comic_collections = {}
        for field_name in ALL_COMIC_COLLECTION_FIELD_NAMES:
            if field_name == "story_arc_numbers":
                related_model = StoryArc
            else:
                related_model = Comic._meta.get_field(field_name).related_model
            deleted_comic_collections[related_model] = set()
        return deleted_comic_collections

    @staticmethod
    def _populate_deleted_comic_collection(deleted_comic_collections, comic) -> None:
        for field_name in ALL_COMIC_COLLECTION_FIELD_NAMES:
            if field_name == "story_arc_numbers":
                for san in comic.story_arc_numbers.select_related("story_arc").only(
                    "story_arc"
                ):
                    deleted_comic_collections[StoryArc].add(san.story_arc.pk)
            elif field_name in DIRECT_M2M_COLLECTION_FIELD_NAMES:
                related_model = comic._meta.get_field(field_name).related_model
                for obj in getattr(comic, field_name).only("pk"):
                    deleted_comic_collections[related_model].add(obj.pk)
            else:
                related_model = comic._meta.get_field(field_name).related_model
                related_id = getattr(comic, field_name).pk
                deleted_comic_collections[related_model].add(related_id)

    @classmethod
    def _populate_deleted_comic_collections(
        cls, delete_qs, deleted_comic_collections
    ) -> None:
        """Populate changed collections for cover timestamp updater."""
        comics_deleted_qs = delete_qs.only(
            *ALL_COMIC_COLLECTION_FIELD_NAMES
        ).prefetch_related(
            "story_arc_numbers__story_arc", *DIRECT_M2M_COLLECTION_FIELD_NAMES
        )
        for comic in comics_deleted_qs.iterator(
            chunk_size=IMPORTER_DELETE_MAX_CHUNK_SIZE
        ):
            cls._populate_deleted_comic_collection(deleted_comic_collections, comic)

    def _warn_on_mass_delete(self, num_deleted: int) -> None:
        """
        Flag a delete large enough to look like the library vanished.

        An unmounted volume or dropped network share makes every path read
        as missing, which the existence backstop cannot tell from a real
        mass deletion. Nothing is blocked here — this only leaves a
        breadcrumb in the log for a user asking where their comics went.
        """
        if num_deleted < _MASS_DELETE_FLOOR:
            return
        total = Comic.objects.filter(library=self.library).count()
        if total and num_deleted >= total * _MASS_DELETE_FRACTION:
            reason = (
                f"Deleting {num_deleted} of {total} comics in"
                f" {self.library.path}. If that library lives on a network"
                f" share or removable volume, check that it is still mounted."
            )
            self.log.warning(reason)

    def bulk_comics_deleted(self, **kwargs) -> tuple[int, dict]:
        """Bulk delete comics found missing from the filesystem."""
        count = 0
        deleted_comic_collections = self._init_deleted_comic_collections()
        status = ImporterRemoveComicsStatus(0, len(self.task.files_deleted))
        try:
            if not self.task.files_deleted:
                return count, deleted_comic_collections
            self.status_controller.start(status)
            # Batch path__in to stay under SQLite's variable limit.
            paths = confirm_deleted(self.task.files_deleted, self.log, "comics")
            self.task.files_deleted = frozenset()
            if not paths:
                return count, deleted_comic_collections
            self._warn_on_mass_delete(len(paths))
            delete_comic_pks: set[int] = set()
            for start in range(0, len(paths), IMPORTER_LINK_FK_BATCH_SIZE):
                if self.abort_event.is_set():
                    break
                batch_paths = paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
                delete_qs = Comic.objects.filter(
                    library=self.library, path__in=batch_paths
                )
                self._populate_deleted_comic_collections(
                    delete_qs, deleted_comic_collections
                )
                delete_comic_pks.update(delete_qs.values_list("pk", flat=True))
                delete_qs.delete()

            count = len(delete_comic_pks)
            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return count, deleted_comic_collections
