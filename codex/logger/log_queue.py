"""Central logging queue."""
import logging

from multiprocessing import Queue


VERBOSE: int = int((logging.INFO + logging.DEBUG) / 2)
LOG_QUEUE = Queue()


class CodexLogger(logging.Logger):
    """Custom logger."""

    def verbose(self, message, *args, **kwargs) -> None:
        """Verbose logging level function."""
        if self.isEnabledFor(VERBOSE):
            self._log(VERBOSE, message, args, **kwargs)


logging.setLoggerClass(CodexLogger)
logging.addLevelName(VERBOSE, "VERBOSE")
logging.VERBOSE = VERBOSE  # type: ignore
