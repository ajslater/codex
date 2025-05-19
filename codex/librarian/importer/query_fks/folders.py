"""Query the missing foreign keys for folders."""

from pathlib import Path

from codex.librarian.importer.const import (
    FK_CREATE,
    FKC_FOLDER_PATHS,
)
from codex.librarian.importer.query_fks.simple import QueryForeignKeysSimpleImporter
from codex.models import Folder


class QueryForeignKeysFoldersImporter(QueryForeignKeysSimpleImporter):
    """Methods for querying missing folders."""

    def query_missing_folder_paths(
        self,
        comic_paths,
        status,
    ):
        """Find missing folder paths."""
        # Get the proposed folder_paths
        library_path = Path(self.library.path)
        proposed_folder_paths = set()
        for comic_path in comic_paths:
            for path in Path(comic_path).parents:
                if path.is_relative_to(library_path):
                    proposed_folder_paths.add(str(path))

        # get the create metadata
        create_folder_paths_dict = {}
        self.query_missing_simple_models(
            proposed_folder_paths,
            create_folder_paths_dict,
            Folder,
            "path",
            status,
        )
        create_folder_paths = create_folder_paths_dict.get(Folder, set())
        return frozenset(create_folder_paths)

    def add_missing_folder_paths(self, comic_paths, status):
        """Add missing folder paths to create set."""
        create_folder_paths = self.query_missing_folder_paths(comic_paths, status)
        """Add missing folder_paths to create fks."""
        if FK_CREATE not in self.metadata:
            self.metadata[FK_CREATE] = {}
        if FKC_FOLDER_PATHS not in self.metadata[FK_CREATE]:
            self.metadata[FK_CREATE][FKC_FOLDER_PATHS] = set()
        self.metadata[FK_CREATE][FKC_FOLDER_PATHS] |= create_folder_paths
        if count := len(create_folder_paths):
            self.log.info(f"Prepared {count} new Folders.")
