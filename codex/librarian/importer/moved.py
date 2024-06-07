"""Bulk import and move comics and folders."""

from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.importer.aggregate import AggregateMetadataImporter
from codex.librarian.importer.const import (
    BULK_UPDATE_FOLDER_MODIFIED_FIELDS,
    CLASS_CUSTOM_COVER_GROUP_MAP,
    CUSTOM_COVER_UPDATE_FIELDS,
    FOLDERS_FIELD,
    LINK_COVER_PKS,
    MOVED_BULK_COMIC_UPDATE_FIELDS,
    MOVED_BULK_FOLDER_UPDATE_FIELDS,
    PARENT_FOLDER,
)
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, CustomCover, Folder
from codex.status import Status


class MovedImporter(AggregateMetadataImporter):
    """Methods for moving comics and folders."""

    def _bulk_comics_moved(self):
        """Move comcis."""
        num_files_moved = len(self.task.files_moved)
        if not num_files_moved:
            return
        status = Status(ImportStatusTypes.FILES_MOVED, 0, num_files_moved)
        self.status_controller.start(status)

        # Prepare FKs
        create_folder_paths = set()
        self.query_missing_folder_paths(create_folder_paths, status)
        self.bulk_folders_create(frozenset(create_folder_paths), status)

        # Update Comics
        comics = Comic.objects.filter(
            library=self.library, path__in=self.task.files_moved.keys()
        ).only("pk", "path", PARENT_FOLDER, FOLDERS_FIELD)

        folder_m2m_links = {}
        updated_comics = []
        for comic in comics.iterator():
            try:
                new_path = self.task.files_moved[comic.path]
                comic.path = new_path
                new_path = Path(new_path)
                comic.parent_folder = Folder.objects.get(  # type: ignore
                    path=new_path.parent
                )
                comic.updated_at = Now()
                comic.presave()
                folder_m2m_links[comic.pk] = Folder.objects.filter(
                    path__in=new_path.parents
                ).values_list("pk", flat=True)
                updated_comics.append(comic)
            except Exception:
                self.log.exception(f"moving {comic.path}")
        self.task.files_moved = {}

        Comic.objects.bulk_update(updated_comics, MOVED_BULK_COMIC_UPDATE_FIELDS)

        # Update m2m field
        if folder_m2m_links:
            self.bulk_fix_comic_m2m_field(FOLDERS_FIELD, folder_m2m_links, status)
        count = len(comics)
        if count:
            self.log.info(f"Moved {count} comics.")

        self.changed += count
        self.status_controller.finish(status)

    def _bulk_covers_moved_prepare(self, status):
        """Create an update map for bulk update."""
        covers = CustomCover.objects.filter(
            library=self.library, path__in=self.task.covers_moved.keys()
        ).only("pk", "path")

        if status:
            status.total = covers.count()

        moved_covers = []
        unlink_pks = set()
        for cover in covers.iterator():
            try:
                new_path = self.task.covers_moved[cover.path]
                cover.path = new_path
                new_path = Path(new_path)
                cover.updated_at = Now()
                cover.presave()
                moved_covers.append(cover)
                unlink_pks.add(cover.pk)
            except Exception:
                self.log.exception(f"moving {cover.path}")
        return moved_covers, unlink_pks

    def _bulk_covers_moved_unlink(self, unlink_pks):
        """Unlink moved covers because they could have moved between group dirs."""
        if not unlink_pks:
            return
        self.log.debug(f"Unlinking {len(unlink_pks)} moved custom covers.")
        for model in CLASS_CUSTOM_COVER_GROUP_MAP:
            groups = model.objects.filter(custom_cover__in=unlink_pks)
            unlink_groups = []
            for group in groups:
                group.custom_cover = None
                unlink_groups.append(group)
            if unlink_groups:
                model.objects.bulk_update(unlink_groups, ["custom_cover"])
                self.log.debug(
                    f"Unlinked {len(unlink_groups)} {model.__name__} moved custom covers."
                )

        self._remove_covers(unlink_pks, custom=True)  # type: ignore

    def _bulk_covers_moved(self, status=None):
        """Move covers."""
        num_covers_moved = len(self.task.covers_moved)
        if not num_covers_moved:
            return
        status = Status(ImportStatusTypes.COVERS_MOVED, None, num_covers_moved)
        self.status_controller.start(status)

        moved_covers, unlink_pks = self._bulk_covers_moved_prepare(status)
        if LINK_COVER_PKS not in self.metadata:
            self.metadata[LINK_COVER_PKS] = set()
        self.metadata[LINK_COVER_PKS].update(unlink_pks)
        if moved_covers:
            CustomCover.objects.bulk_update(moved_covers, CUSTOM_COVER_UPDATE_FIELDS)

        self._bulk_covers_moved_unlink(unlink_pks)

        count = len(moved_covers)
        if count:
            self.log.info(f"Moved {count} custom covers.")

        self.changed += count
        self.status_controller.finish(status)

    def _get_parent_folders(self, dest_folder_paths, status):
        """Get destination parent folders."""
        # Determine parent folder paths.
        dest_parent_folder_paths = set()
        for dest_folder_path in dest_folder_paths:
            dest_parent_path = str(Path(dest_folder_path).parent)
            if dest_parent_path not in dest_folder_paths:
                dest_parent_folder_paths.add(dest_parent_path)

        # Create only intermediate subfolders.
        existing_folder_paths = Folder.objects.filter(
            library=self.library, path__in=dest_parent_folder_paths
        ).values_list("path", flat=True)
        create_folder_paths = frozenset(
            dest_parent_folder_paths - frozenset(existing_folder_paths)
        )
        self.bulk_folders_create(create_folder_paths, status)

        # get parent folders path to model obj dict
        dest_parent_folders_objs = Folder.objects.filter(
            path__in=dest_parent_folder_paths
        ).only("path", "pk")
        dest_parent_folders = {}
        for folder in dest_parent_folders_objs.iterator():
            dest_parent_folders[folder.path] = folder
        return dest_parent_folders

    def bulk_folders_moved(self):
        """Move folders in the database instead of recreating them."""
        num_dirs_moved = len(self.task.dirs_moved)
        if not num_dirs_moved:
            return
        status = Status(ImportStatusTypes.DIRS_MOVED, None, num_dirs_moved)
        self.status_controller.start(status)

        dest_folder_paths = frozenset(self.task.dirs_moved.values())
        dest_parent_folders = self._get_parent_folders(dest_folder_paths, status)

        src_folder_paths = frozenset(self.task.dirs_moved.keys())
        folders_to_move = Folder.objects.filter(
            library=self.library, path__in=src_folder_paths
        ).order_by("path")

        update_folders = []
        for folder in folders_to_move.iterator():
            new_path = self.task.dirs_moved[folder.path]
            folder.name = Path(new_path).name
            folder.path = new_path
            parent_path_str = str(Path(new_path).parent)
            folder.parent_folder = dest_parent_folders.get(parent_path_str)
            folder.presave()
            folder.updated_at = Now()
            update_folders.append(folder)
        self.task.dirs_moved = {}

        update_folders = sorted(update_folders, key=lambda x: len(Path(x.path).parts))

        Folder.objects.bulk_update(update_folders, MOVED_BULK_FOLDER_UPDATE_FIELDS)
        count = len(update_folders)
        if count:
            self.log.info(f"Moved {count} folders.")
        self.changed += count
        self.status_controller.finish(status)

    def _bulk_folders_modified(self):
        """Update folders stat and nothing else."""
        num_dirs_modified = len(self.task.dirs_modified)
        if not num_dirs_modified:
            return
        status = Status(ImportStatusTypes.DIRS_MODIFIED, None, num_dirs_modified)
        self.status_controller.start(status)

        folders = Folder.objects.filter(
            library=self.library, path__in=self.task.dirs_modified
        ).only("stat", "updated_at")
        self.task.dirs_modified = frozenset()
        update_folders = []
        for folder in folders.iterator():
            if Path(folder.path).exists():
                folder.updated_at = Now()
                folder.presave()
                update_folders.append(folder)
        Folder.objects.bulk_update(
            update_folders, fields=BULK_UPDATE_FOLDER_MODIFIED_FIELDS
        )
        count = len(update_folders)
        if count:
            self.log.info(f"Modified {count} folders")
        self.changed += count
        self.status_controller.finish(status)

    def move_and_modify_dirs(self):
        """Move files and dirs and modify dirs."""
        self.bulk_folders_moved()
        self._bulk_comics_moved()
        self._bulk_covers_moved()
        self._bulk_folders_modified()
