"""Librarian Status for imports."""
from enum import Enum
from time import time
from typing import Callable, Union

from django.db.models import Choices

from codex.status import Status


class ImportStatusTypes(Choices):
    """Keys for Import tasks."""

    DIRS_MOVED = "IDM"
    FILES_MOVED = "IFM"
    AGGREGATE_TAGS = "ITR"
    QUERY_MISSING_FKS = "ITQ"
    CREATE_FKS = "ITC"
    DIRS_MODIFIED = "IDU"
    FILES_MODIFIED = "IFU"
    FILES_CREATED = "IFC"
    QUERY_M2M_FIELDS = "IMQ"
    LINK_M2M_FIELDS = "IMC"
    DIRS_DELETED = "IDD"
    FILES_DELETED = "IFD"
    FAILED_IMPORTS = "IFI"


def status_notify(status_type: Union[str, Enum] = "", updates=True):
    """Wrap a function with status changes."""
    # https://stackoverflow.com/questions/5929107/decorators-with-parameters

    def decorator(func) -> Callable[..., int]:
        def wrapper(self, data, *args, status=None, **kwargs) -> int:
            """Run a function bracketed by status changes."""
            num_elements = len(data)
            if not num_elements:
                return 0

            if status:
                finish = False
            else:
                complete = 0 if updates else None
                status = Status(status_type, complete, num_elements, time())
                self.status_controller.start(status)
                finish = True

            kwargs["status"] = status
            try:
                count = func(self, data, *args, **kwargs)
            finally:
                if finish:
                    self.status_controller.finish(status)

            return count

        return wrapper

    return decorator
