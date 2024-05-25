"""Clean up the database after moves or imports."""

from codex.librarian.covers.tasks import CoverRemoveTask
from codex.librarian.importer.const import COMIC_GROUP_FIELD_NAMES
from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import Comic, Folder, StoryArc
from codex.models.paths import CustomCover
from codex.settings.settings import MAX_CHUNK_SIZE
from codex.threads import QueuedThread


class DeletedMixin(QueuedThread):
    """Clean up database methods."""

    def _remove_covers(self, delete_pks, custom=False):
        task = CoverRemoveTask(delete_pks, custom)
        self.librarian_queue.put(task)

    @status_notify(status_type=ImportStatusTypes.DIRS_DELETED, updates=False)
    def _bulk_folders_deleted(self, delete_folder_paths, library, **kwargs):
        """Bulk delete folders."""
        if not delete_folder_paths:
            return 0
        folders = Folder.objects.filter(library=library, path__in=delete_folder_paths)
        delete_comic_pks = frozenset(
            Comic.objects.filter(library=library, folders__in=folders)
            .distinct()
            .values_list("pk", flat=True)
        )
        folders.delete()

        self._remove_covers(delete_comic_pks)

        count = len(delete_folder_paths)
        if count:
            self.log.info(
                f"Deleted {count} folders and {len(delete_comic_pks)} comics"
                f"from {library.path}"
            )
        return count

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

    @staticmethod
    def _init_deleted_comic_groups(deleted_comic_groups):
        """Init deleted_comic_groups, used later even if no deletes."""
        for field_name in COMIC_GROUP_FIELD_NAMES:
            related_model = Comic._meta.get_field(field_name).related_model
            deleted_comic_groups[related_model] = set()

    @status_notify(status_type=ImportStatusTypes.FILES_DELETED, updates=False)
    def _bulk_comics_deleted(
        self, delete_comic_paths, library, deleted_comic_groups, **kwargs
    ):
        """Bulk delete comics found missing from the filesystem."""
        if not delete_comic_paths:
            return 0
        delete_qs = Comic.objects.filter(library=library, path__in=delete_comic_paths)

        self._populate_deleted_comic_groups(delete_qs, deleted_comic_groups)

        delete_comic_pks = frozenset(delete_qs.values_list("pk", flat=True))
        delete_qs.delete()

        self._remove_covers(delete_comic_pks)

        count = len(delete_comic_paths)
        if count:
            self.log.info(f"Deleted {count} comics from {library.path}")

        return count

    @status_notify(status_type=ImportStatusTypes.COVERS_DELETED, updates=False)
    def _bulk_covers_deleted(self, delete_cover_paths, library, **kwargs):
        """Bulk delete comics found missing from the filesystem."""
        if not delete_cover_paths:
            return 0
        covers = CustomCover.objects.filter(
            library=library, path__in=delete_cover_paths
        )
        delete_cover_pks = frozenset(covers.values_list("pk", flat=True))
        covers.delete()

        self._remove_covers(delete_cover_pks, custom=True)

        count = len(delete_cover_paths)
        if count:
            self.log.info(f"Deleted {count} custom covers from {library.path}")

        return count

    def delete(self, library, task, deleted_comic_groups):
        """Delete files and folders."""
        count = self._bulk_folders_deleted(task.dirs_deleted, library)
        task.dirs_deleted = None

        self._init_deleted_comic_groups(deleted_comic_groups)
        count += self._bulk_comics_deleted(
            task.files_deleted, library, deleted_comic_groups
        )
        task.files_deleted = None

        count += self._bulk_covers_deleted(task.covers_deleted, library)
        task.covers_deleted = None

        return count
