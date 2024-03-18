"""Bulk import and move comics and folders."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.const import FOLDERS_FIELD, PARENT_FOLDER
from codex.librarian.importer.create_comics import CreateComicsMixin
from codex.librarian.importer.create_fks import (
    BULK_UPDATE_FOLDER_MODIFIED_FIELDS,
    CreateForeignKeysMixin,
)
from codex.librarian.importer.query_fks import QueryForeignKeysMixin
from codex.librarian.importer.status import ImportStatusTypes, status_notify
from codex.models import Comic, Folder, Library

_MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder")
_MOVED_BULK_FOLDER_UPDATE_FIELDS = ("path", "parent_folder", "name")


class MovedMixin(CreateComicsMixin, CreateForeignKeysMixin, QueryForeignKeysMixin):
    """Methods for moving comics and folders."""

    @status_notify(status_type=ImportStatusTypes.FILES_MOVED, updates=False)
    def _bulk_comics_moved(self, moved_paths, library, status=None):
        """Move comcis."""
        count = 0
        if not moved_paths:
            return count

        # Prepare FKs
        create_folder_paths = set()
        self.query_missing_folder_paths(
            moved_paths.values(), library.path, create_folder_paths, status=status
        )
        self.bulk_folders_create(create_folder_paths, library, status=status)

        # Update Comics
        comics = Comic.objects.filter(
            library=library, path__in=moved_paths.keys()
        ).only("pk", "path", PARENT_FOLDER, FOLDERS_FIELD)

        folder_m2m_links = {}
        now = Now()
        updated_comics = []
        for comic in comics.iterator():
            try:
                new_path = moved_paths[comic.path]
                comic.path = new_path
                new_path = Path(new_path)
                comic.parent_folder = Folder.objects.get(  # type: ignore
                    path=new_path.parent
                )
                comic.updated_at = now
                comic.set_stat()
                folder_m2m_links[comic.pk] = Folder.objects.filter(
                    path__in=new_path.parents
                ).values_list("pk", flat=True)
                updated_comics.append(comic)
            except Exception:
                self.log.exception(f"moving {comic.path}")

        Comic.objects.bulk_update(updated_comics, _MOVED_BULK_COMIC_UPDATE_FIELDS)

        # Update m2m field
        if folder_m2m_links:
            self.bulk_fix_comic_m2m_field(FOLDERS_FIELD, folder_m2m_links, None)
        count = len(comics)
        if count:
            self.log.info(f"Moved {count} comics.")

        return count

    def _get_parent_folders(self, library, dest_folder_paths, status):
        """Get destination parent folders."""
        # Determine parent folder paths.
        dest_parent_folder_paths = set()
        for dest_folder_path in dest_folder_paths:
            dest_parent_path = str(Path(dest_folder_path).parent)
            if dest_parent_path not in dest_folder_paths:
                dest_parent_folder_paths.add(dest_parent_path)

        # Create only intermediate subfolders.
        existing_folder_paths = Folder.objects.filter(
            library=library, path__in=dest_parent_folder_paths
        ).values_list("path", flat=True)
        create_folder_paths = frozenset(
            dest_parent_folder_paths - frozenset(existing_folder_paths)
        )
        self.bulk_folders_create(create_folder_paths, library, status=status)

        # get parent folders path to model obj dict
        dest_parent_folders_objs = Folder.objects.filter(
            path__in=dest_parent_folder_paths
        ).only("path", "pk")
        dest_parent_folders = {}
        for folder in dest_parent_folders_objs.iterator():
            dest_parent_folders[folder.path] = folder
        return dest_parent_folders

    @status_notify(status_type=ImportStatusTypes.DIRS_MOVED, updates=False)
    def _bulk_folders_moved(self, folders_moved, library, **kwargs):
        """Move folders in the database instead of recreating them."""
        if not folders_moved:
            return 0

        dest_folder_paths = frozenset(folders_moved.values())
        status = kwargs.get("status")
        dest_parent_folders = self._get_parent_folders(
            library, dest_folder_paths, status
        )

        src_folder_paths = frozenset(folders_moved.keys())
        folders_to_move = Folder.objects.filter(
            library=library, path__in=src_folder_paths
        ).order_by("path")

        update_folders = []
        now = Now()
        for folder in folders_to_move.iterator():
            new_path = folders_moved[folder.path]
            folder.name = Path(new_path).name
            folder.path = new_path
            parent_path_str = str(Path(new_path).parent)
            folder.parent_folder = dest_parent_folders.get(parent_path_str)
            folder.set_stat()
            folder.updated_at = now  # type: ignore
            update_folders.append(folder)

        update_folders = sorted(update_folders, key=lambda x: len(Path(x.path).parts))

        Folder.objects.bulk_update(update_folders, _MOVED_BULK_FOLDER_UPDATE_FIELDS)
        count = len(update_folders)
        if count:
            self.log.info(f"Moved {count} folders.")
        return count

    @status_notify(status_type=ImportStatusTypes.DIRS_MODIFIED, updates=False)
    def bulk_folders_modified(self, paths, library, **kwargs):
        """Update folders stat and nothing else."""
        count = 0
        if not paths:
            return count
        folders = Folder.objects.filter(library=library, path__in=paths).only(
            "stat", "updated_at"
        )
        update_folders = []
        now = Now()
        for folder in folders.iterator():
            if Path(folder.path).exists():
                folder.set_stat()
                folder.updated_at = now
                update_folders.append(folder)
        Folder.objects.bulk_update(
            update_folders, fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS
        )
        count += len(update_folders)
        if count:
            self.log.info(f"Modified {count} folders")
        return count

    def adopt_orphan_folders(self):
        """Find orphan folders and move them into their correct place."""
        libraries = Library.objects.only("pk", "path")
        for library in libraries.iterator():
            orphan_folder_paths = (
                Folder.objects.filter(library=library, parent_folder=None)
                .exclude(path=library.path)
                .values_list("path", flat=True)
            )

            folders_moved = {}
            for path in orphan_folder_paths:
                folders_moved[path] = path

            self._bulk_folders_moved(folders_moved, library)

    def move_and_modify_dirs(self, library, task):
        """Move files and dirs and modify dirs."""
        changed = 0
        changed += self._bulk_folders_moved(task.dirs_moved, library)
        task.dirs_moved = None

        changed += self._bulk_comics_moved(task.files_moved, library)
        task.files_moved = None

        changed += self.bulk_folders_modified(task.dirs_modified, library)
        task.dirs_modified = None

        return changed
