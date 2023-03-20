"""Librarian Status for imports."""
from dataclasses import dataclass
from typing import Optional

from codex.librarian.status import StatusTypes


class ImportStatusTypes(StatusTypes):
    """Keys for Import tasks."""

    DIRS_MOVED = "Move folders"
    FILES_MOVED = "Move books"
    AGGREGATE_TAGS = "Read tags"
    QUERY_MISSING_FKS = "Discover missing tags"
    CREATE_FKS = "Create new tags"
    DIRS_MODIFIED = "Modify folders"
    FILES_MODIFIED = "Modify books"
    FILES_CREATED = "Create books"
    QUERY_M2M_FIELDS = "Prepare tags for book linking"
    LINK_M2M_FIELDS = "Link books to tags"
    DIRS_DELETED = "Delete folders"
    FILES_DELETED = "Delete books"
    FAILED_IMPORTS = "Record import failures"


@dataclass
class StatusArgs:
    """Args for passing into import functions."""

    count: Optional[int] = None
    total: Optional[int] = None
    since: float = 0
    status: str = ""  # TODO? use this?
