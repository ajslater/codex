"""Clean up the database after moves or imports."""

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.cache import CacheUpdateImporter
from codex.librarian.importer.const import COMIC_GROUP_FIELD_NAMES
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, Folder, StoryArc
from codex.models.paths import CustomCover
from codex.settings.settings import MAX_CHUNK_SIZE
from codex.status import Status


class DeletedImporter(CacheUpdateImporter):
    """Clean up database methods."""

    def _remove_covers(self, delete_pks, custom=False):
        task = CoverRemoveTask(delete_pks, custom)
        self.librarian_queue.put(task)

    def _bulk_folders_deleted(self, **kwargs):
        """Bulk delete folders."""
        if not self.task.dirs_deleted:
            return 0
        status = Status(ImportStatusTypes.DIRS_DELETED, 0, len(self.task.dirs_deleted))
        self.status_controller.start(status)
        folders = Folder.objects.filter(
            library=self.library, path__in=self.task.dirs_deleted
        )
        self.task.dirs_deleted = frozenset()
        delete_comic_pks = frozenset(
            Comic.objects.filter(library=self.library, folders__in=folders)
            .distinct()
            .values_list("pk", flat=True)
        )
        folders.delete()

        self._remove_covers(delete_comic_pks)

        count = len(delete_comic_pks)
        if count:
            self.log.info(
                f"Deleted {count} folders and {len(delete_comic_pks)} comics"
                f"from {self.library.path}"
            )
        self.status_controller.finish(status)
        return count

    @staticmethod
    def _init_deleted_comic_groups():
        """Init deleted_comic_groups, used later even if no deletes."""
        deleted_comic_groups = {}
        for field_name in COMIC_GROUP_FIELD_NAMES:
            if field_name == "story_arc_numbers":
                related_model = StoryArc
            else:
                related_model = Comic._meta.get_field(field_name).related_model
            deleted_comic_groups[related_model] = set()
        return deleted_comic_groups

    @staticmethod
    def _populate_deleted_comic_groups(delete_qs, deleted_comic_groups):
        """Populate changed groups for cover timestamp updater."""
        comics_deleted_qs = delete_qs.only(*COMIC_GROUP_FIELD_NAMES).prefetch_related(
            "story_arc_numbers__story_arc"
        )
        for comic in comics_deleted_qs.iterator(chunk_size=MAX_CHUNK_SIZE):
            for field_name in COMIC_GROUP_FIELD_NAMES:
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

    def _bulk_comics_deleted(self, deleted_comic_groups, **kwargs):
        """Bulk delete comics found missing from the filesystem."""
        if not self.task.files_deleted:
            return 0
        status = Status(
            ImportStatusTypes.FILES_DELETED, 0, len(self.task.files_deleted)
        )
        self.status_controller.start(status)
        delete_qs = Comic.objects.filter(
            library=self.library, path__in=self.task.files_deleted
        )
        self.task.files_deleted = frozenset()

        self._populate_deleted_comic_groups(delete_qs, deleted_comic_groups)

        delete_comic_pks = frozenset(delete_qs.values_list("pk", flat=True))
        delete_qs.delete()

        self._remove_covers(delete_comic_pks)

        count = len(delete_comic_pks)
        if count:
            self.log.info(f"Deleted {count} comics from {self.library.path}")
        self.status_controller.finish(status)
        return count

    def _bulk_covers_deleted(self, **kwargs):
        """Bulk delete comics found missing from the filesystem."""
        if not self.task.covers_deleted:
            return 0
        status = Status(
            ImportStatusTypes.COVERS_DELETED, 0, len(self.task.covers_deleted)
        )
        self.status_controller.start(status)
        covers = CustomCover.objects.filter(
            library=self.library, path__in=self.task.covers_deleted
        )
        self.task.covers_deleted = frozenset()
        delete_cover_pks = frozenset(covers.values_list("pk", flat=True))
        covers.delete()

        self._remove_covers(delete_cover_pks, custom=True)

        count = len(delete_cover_pks)
        if count:
            self.log.info(f"Deleted {count} custom covers from {self.library.path}")

        self.status_controller.finish(status)
        return count

    def delete(self):
        """Delete files and folders."""
        count = self._bulk_folders_deleted()
        deleted_comic_groups = self._init_deleted_comic_groups()
        count += self._bulk_comics_deleted(deleted_comic_groups)
        count += self._bulk_covers_deleted()
        self.changed += count
        return deleted_comic_groups
