"""Clean up the database after moves or imports."""

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.scribe.importer.const import ALL_COMIC_GROUP_FIELD_NAMES
from codex.librarian.scribe.importer.finish import FinishImporter
from codex.librarian.scribe.status import ScribeStatusTypes
from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.librarian.status import Status
from codex.models import Comic, Folder, StoryArc
from codex.models.paths import CustomCover
from codex.settings import MAX_CHUNK_SIZE


class DeletedImporter(FinishImporter):
    """Clean up database methods."""

    def _remove_covers(self, delete_pks, *, custom: bool):
        task = CoverRemoveTask(delete_pks, custom)
        self.librarian_queue.put(task)

    def _bulk_folders_deleted(self, **kwargs):
        """Bulk delete folders."""
        status = Status(
            ScribeStatusTypes.REMOVE_FOLDERS, 0, len(self.task.dirs_deleted)
        )
        try:
            if not self.task.dirs_deleted:
                return 0
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
            count, _ = folders.delete()

            self._remove_covers(delete_comic_pks, custom=False)

            level = "INFO" if count else "DEBUG"
            reason = f"Deleted {count} folders from {self.library.path}"
            self.log.log(level, reason)
        finally:
            self.status_controller.finish(status)
        return count

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
    def _populate_deleted_comic_groups(delete_qs, deleted_comic_groups):
        """Populate changed groups for cover timestamp updater."""
        comics_deleted_qs = delete_qs.only(
            *ALL_COMIC_GROUP_FIELD_NAMES
        ).prefetch_related("story_arc_numbers__story_arc")
        for comic in comics_deleted_qs.iterator(chunk_size=MAX_CHUNK_SIZE):
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

    def _bulk_comics_deleted(self, deleted_comic_groups, **kwargs):
        """Bulk delete comics found missing from the filesystem."""
        status = Status(
            ScribeStatusTypes.REMOVE_COMICS, 0, len(self.task.files_deleted)
        )
        try:
            if not self.task.files_deleted:
                return 0
            self.status_controller.start(status)
            delete_qs = Comic.objects.filter(
                library=self.library, path__in=self.task.files_deleted
            )
            self.task.files_deleted = frozenset()

            self._populate_deleted_comic_groups(delete_qs, deleted_comic_groups)

            delete_comic_pks = frozenset(delete_qs.values_list("pk", flat=True))
            count, _ = delete_qs.delete()

            self._remove_covers(delete_comic_pks, custom=False)

            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Deleted {count} comics from {self.library.path}")
        finally:
            self.status_controller.finish(status)
        return count

    def _bulk_covers_deleted(self, **kwargs):
        """Bulk delete comics found missing from the filesystem."""
        status = Status(
            ScribeStatusTypes.REMOVE_CUSTOM_COVERS, 0, len(self.task.covers_deleted)
        )
        try:
            if not self.task.covers_deleted:
                return 0
            self.status_controller.start(status)
            covers = CustomCover.objects.filter(
                library=self.library, path__in=self.task.covers_deleted
            )
            self.task.covers_deleted = frozenset()
            delete_cover_pks = frozenset(covers.values_list("pk", flat=True))
            count, _ = covers.delete()

            self._remove_covers(delete_cover_pks, custom=True)

            level = "INFO" if count else "DEBUG"
            self.log.log(
                level, f"Deleted {count} custom covers from {self.library.path}"
            )
        finally:
            self.status_controller.finish(status)

        return count

    def delete(self):
        """Delete files and folders."""
        self.counts.folders_deleted += self._bulk_folders_deleted()
        deleted_comic_groups = self._init_deleted_comic_groups()
        self.counts.comics_deleted = self._bulk_comics_deleted(deleted_comic_groups)
        self.counts.covers_deleted = self._bulk_covers_deleted()
        timestamp_updater = TimestampUpdater(self.log, self.librarian_queue)
        timestamp_updater.update_library_groups(
            self.library, self.start_time, deleted_comic_groups
        )
