"""Bulk import and move comics."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.scribe.importer.const import (
    CREATE_FKS,
    FOLDERS_FIELD_NAME,
    MOVED_BULK_COMIC_UPDATE_FIELDS,
    PARENT_FOLDER_FIELD_NAME,
    PATH_FIELD_NAME,
)
from codex.librarian.scribe.importer.read import ReadMetadataImporter
from codex.librarian.scribe.importer.statii.create import ImporterCreateTagsStatus
from codex.librarian.scribe.importer.statii.moved import ImporterMoveComicsStatus
from codex.librarian.scribe.importer.statii.query import ImporterQueryMissingTagsStatus
from codex.models import Comic, Folder


class MovedComicsImporter(ReadMetadataImporter):
    """Methods for moving comics and folders."""

    def _bulk_comics_moved_ensure_folders(self):
        """Ensure folders we're moving to exist."""
        dest_comic_paths = self.task.files_moved.values()
        dest_comic_paths = self.get_all_library_relative_paths(dest_comic_paths)
        num_dest_comic_paths = len(dest_comic_paths)
        if not num_dest_comic_paths:
            return
        # Not sending statues to the controller for now.
        status = ImporterQueryMissingTagsStatus()
        if CREATE_FKS not in self.metadata:
            self.metadata[CREATE_FKS] = {}
        proposed_values_map = {path: set() for path in dest_comic_paths}
        self.query_missing_models(
            Folder,
            proposed_values_map,
            status,
        )
        create_folder_paths = self.metadata[CREATE_FKS].pop(Folder, {})
        count = len(create_folder_paths)
        if not count:
            return
        status = ImporterCreateTagsStatus(0, count)
        self.log.debug(
            "Creating {count} folders for {num_dest_comic_paths} moved comics."
        )
        self.bulk_folders_create(create_folder_paths, status)
        self.status_controller.finish(status)

    def _prepare_moved_comic(
        self, comic, folder_m2m_links, updated_comics, del_folder_rows
    ):
        """Prepare one comic for bulk update."""
        try:
            new_path = self.task.files_moved[comic.path]
            old_folder_pks = frozenset(folder.pk for folder in comic.folders.all())
            comic.path = new_path
            new_path = Path(new_path)
            comic.parent_folder = Folder.objects.get(path=new_path.parent)
            comic.updated_at = Now()
            comic.presave()
            new_folder_pks = frozenset(
                Folder.objects.filter(path__in=new_path.parents).values_list(
                    "pk", flat=True
                )
            )
            folder_m2m_links[comic.pk] = new_folder_pks
            updated_comics.append(comic)
            if del_folder_pks := old_folder_pks - new_folder_pks:
                for pk in del_folder_pks:
                    del_folder_rows.append((comic.pk, pk))
        except Exception:
            self.log.exception(f"moving {comic.path}")

    def _bulk_comics_move_prepare(self):
        """Prepare Update Comics."""
        comics = (
            Comic.objects.prefetch_related(FOLDERS_FIELD_NAME)
            .filter(library=self.library, path__in=self.task.files_moved.keys())
            .only(PATH_FIELD_NAME, PARENT_FOLDER_FIELD_NAME, FOLDERS_FIELD_NAME)
        )

        folder_m2m_links = {}
        updated_comics = []
        del_folder_rows = []
        for comic in comics:
            self._prepare_moved_comic(
                comic, folder_m2m_links, updated_comics, del_folder_rows
            )
        self.task.files_moved = {}
        self.log.debug(f"Prepared {len(updated_comics)} for move...")
        del_rows_map = {}
        if del_folder_rows:
            del_rows_map[FOLDERS_FIELD_NAME] = del_folder_rows
        return updated_comics, folder_m2m_links, del_rows_map

    def bulk_comics_moved(self):
        """Move comcis."""
        num_files_moved = len(self.task.files_moved)
        status = ImporterMoveComicsStatus(0, num_files_moved)
        try:
            if not num_files_moved:
                return 0
            self.status_controller.start(status)

            # Prepare
            self._bulk_comics_moved_ensure_folders()
            updated_comics, folder_m2m_links, del_rows_map = (
                self._bulk_comics_move_prepare()
            )

            # Update comics
            # Potentially could just add these to the right structures and do it later during create and link.
            Comic.objects.bulk_update(updated_comics, MOVED_BULK_COMIC_UPDATE_FIELDS)
            if del_rows_map:
                self.delete_m2m_field(FOLDERS_FIELD_NAME, del_rows_map, status)
            if folder_m2m_links:
                self.link_comic_m2m_field(FOLDERS_FIELD_NAME, folder_m2m_links, status)

            count = len(updated_comics)
        finally:
            self.status_controller.finish(status)
        return count
