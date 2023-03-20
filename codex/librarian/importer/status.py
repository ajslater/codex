"""Librarian Status for imports."""
from dataclasses import dataclass
from time import time
from typing import Callable, Optional

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
    status: str = ""


def status(status="", updates=True):
    """Wrap a function with status changes."""
    # https://stackoverflow.com/questions/5929107/decorators-with-parameters

    def decorator(func) -> Callable[..., int]:
        def wrapper(self, data, *args, status_args=None, **kwargs) -> int:
            """Run a function bracketed by status changes."""
            num_elements = len(data)
            if not num_elements:
                return 0

            if status_args:
                finish = False
            else:
                complete = 0 if updates else None
                status_args = StatusArgs(complete, num_elements, time(), status)
                self.status_controller.start(
                    status_args.status, status_args.count, status_args.total
                )
                finish = True

            kwargs["status_args"] = status_args
            try:
                count = func(self, data, *args, **kwargs)
            finally:
                if finish:
                    self.status_controller.finish(status)

            return count

        return wrapper

    return decorator
