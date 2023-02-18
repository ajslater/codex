"""Bulk import and move comics and folders."""
import logging
from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.create_comics import CreateComicsMixin
from codex.librarian.importer.create_fks import CreateForeignKeysMixin
from codex.librarian.importer.query_fks import QueryForeignKeysMixin
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, Folder, Library

MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder")
MOVED_BULK_FOLDER_UPDATE_FIELDS = ("path", "parent_folder", "name")


class MovedMixin(CreateComicsMixin, CreateForeignKeysMixin, QueryForeignKeysMixin):
    """Methods for moving comics and folders."""

    def bulk_comics_moved(self, library, moved_paths):
        """Abbreviated bulk_import_comics to just change path related fields."""
        try:
            self.status_controller.start(
                ImportStatusTypes.FILES_MOVED, len(moved_paths)
            )
            # Prepare FKs
            create_folder_paths = self.query_missing_folder_paths(
                library.path, moved_paths.values()
            )
            self.bulk_folders_create(library, create_folder_paths)

            # Update Comics
            comics = Comic.objects.filter(
                library=library, path__in=moved_paths.keys()
            ).only("pk", "path", "parent_folder", "folders")

            folder_m2m_links = {}
            now = Now()
            comic_pks = []
            for comic in comics:
                try:
                    comic.path = moved_paths[comic.path]
                    new_path = Path(comic.path)
                    if new_path.parent == Path(library.path):
                        comic.parent_folder = None
                    else:
                        comic.parent_folder = Folder.objects.get(  # type: ignore
                            path=new_path.parent
                        )
                    comic.updated_at = now
                    comic.set_stat()
                    folder_m2m_links[comic.pk] = Folder.objects.filter(
                        path__in=new_path.parents
                    ).values_list("pk", flat=True)
                    comic_pks.append(comic.pk)
                except Exception as exc:
                    self.log.error(f"moving {comic.path}: {exc}")

            count = Comic.objects.bulk_update(comics, MOVED_BULK_COMIC_UPDATE_FIELDS)

            # Update m2m field
            if folder_m2m_links:
                self.bulk_recreate_m2m_field("folders", folder_m2m_links)
            if count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"Moved {count} comics.")

            return bool(count)
        finally:
            self.status_controller.finish(ImportStatusTypes.FILES_MOVED)

    def _get_parent_folders(self, library, dest_folder_paths):
        """Get destination parent folders."""
        # Determine parent folder paths.
        dest_parent_folder_paths = set()
        for dest_folder_path in dest_folder_paths:
            dest_parent_path = Path(dest_folder_path).parent
            if dest_parent_path == Path(library.path):
                continue
            dest_parent_folder_paths.add(str(dest_parent_path))

        # Create intermediate subfolders.
        existing_folder_paths = Folder.objects.filter(
            library=library, path__in=dest_parent_folder_paths
        ).values_list("path", flat=True)
        create_folder_paths = frozenset(
            dest_parent_folder_paths - frozenset(existing_folder_paths)
        )
        self.bulk_folders_create(library, create_folder_paths)

        # get parent folders path to model obj dict
        dest_parent_folders_objs = Folder.objects.filter(
            path__in=dest_parent_folder_paths
        ).only("path", "pk")
        dest_parent_folders = {}
        for folder in dest_parent_folders_objs:
            dest_parent_folders[folder.path] = folder
        return dest_parent_folders

    def _update_moved_folders(self, library, folders_moved, dest_parent_folders):
        """Move folders."""
        try:
            src_folder_paths = frozenset(folders_moved.keys())
            folders = Folder.objects.filter(library=library, path__in=src_folder_paths)

            update_folders = []
            now = Now()
            for folder in folders:
                new_path = folders_moved[folder.path]
                folder.name = Path(new_path).name
                folder.path = new_path
                parent_path = str(Path(new_path).parent)
                if parent_path == library.path:
                    folder.parent_folder = None
                else:
                    folder.parent_folder = dest_parent_folders.get(parent_path)
                folder.set_stat()
                folder.updated_at = now  # type: ignore
                update_folders.append(folder)

            update_folders = sorted(
                update_folders, key=lambda x: len(Path(x.path).parts)
            )

            count = Folder.objects.bulk_update(
                update_folders, MOVED_BULK_FOLDER_UPDATE_FIELDS
            )
            if count:
                level = logging.INFO
            else:
                level = logging.DEBUG
            self.log.log(level, f"Moved {count} folders.")
            return bool(count)
        finally:
            self.status_controller.finish(ImportStatusTypes.DIRS_MOVED)

    def bulk_folders_moved(self, library, folders_moved):
        """Move folders in the database instead of recreating them."""
        if not folders_moved:
            return False
        dest_folder_paths = frozenset(folders_moved.values())
        dest_parent_folders = self._get_parent_folders(library, dest_folder_paths)

        return self._update_moved_folders(library, folders_moved, dest_parent_folders)

    def adopt_orphan_folders(self):
        """Find orphan folders and move them into their correct place."""
        libraries = Library.objects.only("pk", "path")
        for library in libraries:
            orphan_folder_paths = (
                Folder.objects.filter(library=library, parent_folder=None)
                .exclude(path=library.path)
                .values_list("path", flat=True)
            )

            folders_moved = {}
            for path in orphan_folder_paths:
                folders_moved[path] = path

            self.bulk_folders_moved(library, folders_moved)
