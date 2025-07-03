"""Aggregate folders and path from path."""

from pathlib import Path

from codex.librarian.scribe.importer.const import (
    FOLDERS_FIELD_NAME,
    LINK_M2MS,
    PATH_FIELD_NAME,
)
from codex.librarian.scribe.importer.read.many_to_many import (
    AggregateManyToManyMetadataImporter,
)
from codex.models.groups import Folder


class AggregatePathMetadataImporter(AggregateManyToManyMetadataImporter):
    """Aggregate path metadata."""

    def get_all_library_relative_paths(self, comic_paths):
        """Get the proposed folder_paths."""
        # also used by moved/comic.py:_bulk_comics_moved_ensure_folders()
        library_path = Path(self.library.path)
        proposed_folder_paths = set()

        for comic_path in comic_paths:
            for path in Path(comic_path).parents:
                if path.is_relative_to(library_path):
                    proposed_folder_paths.add((str(path),))
        return proposed_folder_paths

    def get_path_metadata(self, md: dict, path: Path | str):
        """Set the path metadata."""
        proposed_folder_paths = self.get_all_library_relative_paths((path,))
        for proposed_path in proposed_folder_paths:
            self.add_query_model(Folder, proposed_path)
        self.metadata[LINK_M2MS][path][FOLDERS_FIELD_NAME] = proposed_folder_paths
        md[PATH_FIELD_NAME] = str(path)
