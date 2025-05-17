"""Bulk import and move comics."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.aggregate import AggregateMetadataImporter
from codex.librarian.importer.const import (
    FOLDERS_FIELD,
    MOVED_BULK_COMIC_UPDATE_FIELDS,
    PARENT_FOLDER,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, Folder
from codex.status import Status


class MovedComicsImporter(AggregateMetadataImporter):
    """Methods for moving comics and folders."""

    def _bulk_comics_moved_ensure_folders(self):
        """Ensure folders we're moving to exist."""
        dest_comic_paths = self.task.files_moved.values()
        if not dest_comic_paths:
            return
        # Not sending statues to the controller for now.
        status = Status(ImportStatusTypes.QUERY_MISSING_TAGS)
        create_folder_paths = self.query_missing_folder_paths(dest_comic_paths, status)
        if not create_folder_paths:
            return
        status = Status(ImportStatusTypes.CREATE_TAGS, 0, len(create_folder_paths))
        self.log.debug(
            "Creating {len(create_folder_paths)} folders for {len(dest_comic_paths)} moved comics."
        )
        self.bulk_folders_create(create_folder_paths, status)

    def _prepare_moved_comic(self, comic, folder_m2m_links, updated_comics):
        """Prepare one comic for bulk update."""
        try:
            new_path = self.task.files_moved[comic.path]
            comic.path = new_path
            new_path = Path(new_path)
            comic.parent_folder = Folder.objects.get(path=new_path.parent)
            comic.updated_at = Now()
            comic.presave()
            folder_m2m_links[comic.pk] = Folder.objects.filter(
                path__in=new_path.parents
            ).values_list("pk", flat=True)
            updated_comics.append(comic)
        except Exception:
            self.log.exception(f"moving {comic.path}")

    def _bulk_comics_move_prepare(self):
        """Prepare Update Comics."""
        comics = Comic.objects.filter(
            library=self.library, path__in=self.task.files_moved.keys()
        ).only("pk", "path", PARENT_FOLDER, FOLDERS_FIELD)

        folder_m2m_links = {}
        updated_comics = []
        for comic in comics.iterator():
            self._prepare_moved_comic(comic, folder_m2m_links, updated_comics)
        self.task.files_moved = {}
        self.log.debug(f"Prepared {len(updated_comics)} for move...")
        return updated_comics, folder_m2m_links

    def bulk_comics_moved(self):
        """Move comcis."""
        num_files_moved = len(self.task.files_moved)
        if not num_files_moved:
            return
        status = Status(ImportStatusTypes.MOVE_COMICS, 0, num_files_moved)
        self.status_controller.start(status)

        # Prepare
        self._bulk_comics_moved_ensure_folders()
        updated_comics, folder_m2m_links = self._bulk_comics_move_prepare()

        # Update comics
        Comic.objects.bulk_update(updated_comics, MOVED_BULK_COMIC_UPDATE_FIELDS)
        if folder_m2m_links:
            self.bulk_fix_comic_m2m_field(FOLDERS_FIELD, folder_m2m_links, status)

        count = len(updated_comics)
        if count:
            self.log.success(f"Moved {count} comics.")

        self.changed += count
        self.status_controller.finish(status)
