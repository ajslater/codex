"""Librarian Status for imports."""
from codex.librarian.status import StatusTypes


class ImportStatusTypes(StatusTypes):
    """Keys for Import tasks."""

    # TODO rename consistently
    DIRS_MOVED = "Move folders"
    FILES_MOVED = "Move books"
    AGGREGATE_TAGS = "Read tags"
    QUERY_MISSING_FKS = "Determine missing tags"
    CREATE_FKS = "Create new tags"
    DIRS_MODIFIED = "Modify folders"
    FILES_MODIFIED = "Modify books"
    FILES_CREATED = "Create books"
    QUERY_M2M_FIELDS = "Prepare books for tag linking"
    LINK_M2M_FIELDS = "Link books to tags"
    DIRS_DELETED = "Delete folders"
    FILES_DELETED = "Delete books"
    FAILED_IMPORTS_MODIFIED = "Update persistent Failed Imports"
    CLEAN_FAILED_IMPORTS = "Remove succeeded Failed Imports"
    CREATE_FAILED_IMPORTS = "Record Failed Imports"
