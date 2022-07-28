"""Librarian Status for imports."""


class ImportStatusKeys:
    """Keys for Import tasks."""

    DIRS_MOVED = {"type": "Move folders"}
    FILES_MOVED = {"type": "Move books"}
    FILES_MODIFIED = {"type": "Modify books"}
    FILES_CREATED = {"type": "Create books"}
    DIRS_DELETED = {"type": "Delete folders"}
    FILES_DELETED = {"type": "Delete books"}
    AGGREGATE_STATUS_KEYS = {"type": "Read tags"}
    QUERY_MISSING_FKS = {"type": "Determine missing tags"}
    CREATE_FKS = {"type": "Create tags"}
    LINK_M2M_FIELDS = {"type": "Link books to tags"}
    CLEAN_FAILED_IMPORTS = {"type": "Remove succeeded Failed Imports"}
    CREATE_FAILED_IMPORTS = {"type": "Record Failed Imports"}
    ALL = (
        DIRS_MOVED,
        FILES_MOVED,
        FILES_MODIFIED,
        FILES_CREATED,
        DIRS_DELETED,
        FILES_DELETED,
        AGGREGATE_STATUS_KEYS,
        QUERY_MISSING_FKS,
        CREATE_FKS,
        LINK_M2M_FIELDS,
        CLEAN_FAILED_IMPORTS,
        CREATE_FAILED_IMPORTS,
    )
