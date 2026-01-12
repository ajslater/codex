"""Delete comics methods."""

from codex.librarian.scribe.importer.const import ALL_COMIC_GROUP_FIELD_NAMES
from codex.librarian.scribe.importer.delete.covers import DeletedCoversImporter
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveComicsStatus
from codex.models import Comic, Folder, StoryArc
from codex.settings import DELETE_MAX_CHUNK_SIZE


class DeletedComicsImporter(DeletedCoversImporter):
    """Delete comics methods."""

    @staticmethod
    def _init_deleted_comic_groups():
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
    def _populate_deleted_comic_group(deleted_comic_groups, comic):
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
    def _populate_deleted_comic_groups(cls, delete_qs):
        """Populate changed groups for cover timestamp updater."""
        deleted_comic_groups = cls._init_deleted_comic_groups()
        comics_deleted_qs = delete_qs.only(
            *ALL_COMIC_GROUP_FIELD_NAMES
        ).prefetch_related("story_arc_numbers__story_arc")
        for comic in comics_deleted_qs.iterator(chunk_size=DELETE_MAX_CHUNK_SIZE):
            cls._populate_deleted_comic_group(deleted_comic_groups, comic)
        return deleted_comic_groups

    def bulk_comics_deleted(self, **kwargs) -> tuple[int, dict]:
        """Bulk delete comics found missing from the filesystem."""
        count = 0
        deleted_comic_groups = {}
        status = ImporterRemoveComicsStatus(0, len(self.task.files_deleted))
        try:
            if not self.task.files_deleted:
                return count, deleted_comic_groups
            self.status_controller.start(status)
            delete_qs = Comic.objects.filter(
                library=self.library, path__in=self.task.files_deleted
            )
            self.task.files_deleted = frozenset()

            deleted_comic_groups = self._populate_deleted_comic_groups(delete_qs)

            delete_comic_pks = frozenset(delete_qs.values_list("pk", flat=True))
            delete_qs.delete()
            count = len(delete_comic_pks)

            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return count, deleted_comic_groups
