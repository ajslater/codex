"""Central Logging Thread."""

import logging
from logging.handlers import QueueListener, RotatingFileHandler

from codex.logger.formatter import ColorFormatter
from codex.settings.settings import DEBUG, LOG_DIR, LOG_TO_CONSOLE, LOG_TO_FILE


class CodexLogQueueListener(QueueListener):
    """Host for logging queue listener."""

    _LOG_FMT = "{asctime} {levelname:7} {message}"
    _DEBUG_LOG_FMT = "{asctime} {levelname:7} {name:25} {message}"
    _DATEFMT = "%Y-%m-%d %H:%M:%S %Z"
    _FORMATTER_STYLE = "{"
    _LOG_PATH = LOG_DIR / "codex.log"
    _LOG_MAX_BYTES = 10 * 1024 * 1024

    @classmethod
    def _get_file_log_handler(cls, fmt):
        """Get the log handlers for initialization."""
        handler = None
        try:
            cls._LOG_PATH.parent.mkdir(exist_ok=True, parents=True)
            handler = RotatingFileHandler(
                cls._LOG_PATH, maxBytes=cls._LOG_MAX_BYTES, backupCount=30, delay=True
            )
            formatter = logging.Formatter(
                fmt, style=cls._FORMATTER_STYLE, datefmt=cls._DATEFMT
            )
            handler.setFormatter(formatter)
        except Exception as exc:
            print("ERROR creating file logging handler", exc)
        return handler

    @classmethod
    def _get_console_handler(cls, fmt):
        """Create the console handler."""
        handler = None
        try:
            handler = logging.StreamHandler()
            formatter = ColorFormatter(
                fmt, style=cls._FORMATTER_STYLE, datefmt=cls._DATEFMT
            )
            handler.setFormatter(formatter)
        except Exception as exc:
            print("ERROR creating console logging handler", exc)
        return handler

    @classmethod
    def _get_log_handlers(cls):
        """Get handlers."""
        handlers = []
        fmt = cls._DEBUG_LOG_FMT if DEBUG else cls._LOG_FMT

        if LOG_TO_FILE:
            handlers.append(cls._get_file_log_handler(fmt))
        if LOG_TO_CONSOLE:
            handlers.append(cls._get_console_handler(fmt))
        return handlers

    def __init__(self, log_queue):
        """Start self with handlers."""
        handlers = self._get_log_handlers()
        self.log_queue = log_queue
        super().__init__(log_queue, *handlers)

    def stop(self):
        """Stop listener and cleans up handlers."""
        super().stop()
        for handler in self.handlers:
            handler.flush()
            handler.close()
        self.handlers = ()
        while not self.log_queue.empty():
            self.log_queue.get_nowait()
        self.log_queue.close()
        self.log_queue.join_thread()
