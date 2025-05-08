"""Class to run librarian tasks inline without a thread."""

from multiprocessing import Queue
from typing import TYPE_CHECKING

from codex.logger.logger import get_logger

if TYPE_CHECKING:
    from logging import Logger


class LoggerBaseMixin:
    """A class that holds it's own logger."""

    def init_logger(self, log_queue: Queue):
        """Set up logger."""
        self.log_queue: Queue = log_queue  # pyright: ignore[reportUninitializedInstanceVariable]
        self.log: Logger = get_logger(self.__class__.__name__, log_queue)  # pyright: ignore[reportUninitializedInstanceVariable]
