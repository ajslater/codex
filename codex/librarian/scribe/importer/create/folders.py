"""Create missing folder foreign keys for an import."""

from pathlib import Path

from codex.librarian.scribe.importer.const import BULK_UPDATE_FOLDER_FIELDS
from codex.librarian.scribe.importer.create.covers import CreateCoversImporter
from codex.librarian.status import Status
from codex.models import Folder


class CreateForeignKeysFolderImporter(CreateCoversImporter):
    """Methods for creating foreign keys."""

    def _get_parent_folder(self, path: Path):
        parent = None
        if str(path) == self.library.path:
            return parent
        parent_path = str(path.parent)
        try:
            parent = Folder.objects.get(path=parent_path)
        except Folder.DoesNotExist:
            if path.parent != Path(self.library.path):
                reason = (
                    f"Can't find parent folder {parent_path} for {path} in library"
                    f" {self.library.path}"
                )
                self.log.warning(reason)
        return parent

    def _bulk_folders_create_add_folder(self, path: Path, create_folders):
        """Add one folder to the create list."""
        parent_folder = self._get_parent_folder(path)
        folder = Folder(
            library=self.library,
            path=str(path),
            name=path.name,
            parent_folder=parent_folder,
        )
        folder.presave()
        self.add_custom_cover_to_group(Folder, folder)
        create_folders.append(folder)

    def _bulk_folders_create_depth_level(self, paths, status: Status):
        """Create a depth level of folders."""
        create_folders = []
        for path in sorted(paths):
            self._bulk_folders_create_add_folder(path, create_folders)
        Folder.objects.bulk_create(
            create_folders,
            update_conflicts=True,
            update_fields=BULK_UPDATE_FOLDER_FIELDS,
            unique_fields=Folder._meta.unique_together[0],
        )
        count = len(create_folders)
        status.increment_complete(count)
        self.status_controller.update(status)
        return count

    def bulk_folders_create(self, folder_paths: frozenset, status) -> int:
        """Create folders breadth first."""
        count = 0
        if not folder_paths:
            return count
        # group folder paths by depth
        folder_path_dict = {}
        for path_strs in folder_paths:
            for path_str in path_strs:
                path = Path(path_str)
                path_length = len(path.parts)
                if path_length not in folder_path_dict:
                    folder_path_dict[path_length] = set()
                folder_path_dict[path_length].add(path)

        # create each depth level first to ensure we can assign parents
        for depth_level in sorted(folder_path_dict):
            paths = sorted(folder_path_dict[depth_level])
            level_count = self._bulk_folders_create_depth_level(paths, status)
            count += level_count
            self.log.debug(
                f"Created {level_count} Folders at depth level {depth_level}"
            )

        self.status_controller.update(status)
        return count

    def bulk_folders_update(self, folder_paths: frozenset, status) -> int:
        """Update existing folders."""
        # Is this really moved?
        count = 0
        if not folder_paths:
            return count

        folders = Folder.objects.filter(library=self.library, path__in=folder_paths)
        for folder in folders:
            folder.save()

        self.status_controller.update(status)
        return count
