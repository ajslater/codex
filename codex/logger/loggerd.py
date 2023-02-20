"""Central Logging Thread."""
import logging
from logging.handlers import QueueListener, RotatingFileHandler

from colors import color

from codex.settings.settings import DEBUG, LOG_DIR, LOG_TO_CONSOLE, LOG_TO_FILE


class ColorFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors."""

    FORMAT_COLORS = {
        "CRITICAL": {"fg": "red", "style": "bold"},
        "ERROR": {"fg": "red"},
        "WARNING": {"fg": "yellow"},
        "INFO": {"fg": "green"},
        "DEBUG": {"fg": "black", "style": "bold"},
        "NOTSET": {"fg": "blue"},
    }
    FORMATTERS = {}

    def __init__(self, format, **kwargs):
        """Set up the FORMATS dict."""
        super().__init__(**kwargs)
        for level_name, args in self.FORMAT_COLORS.items():
            levelno = getattr(logging, level_name)
            template = color(format, **args)
            formatter = logging.Formatter(fmt=template, **kwargs)
            self.FORMATTERS[levelno] = formatter

    def format(self, record):
        """Format each log message."""
        formatter = self.FORMATTERS[record.levelno]
        return formatter.format(record)


class CodexLogQueueListener(QueueListener):
    """Host for logging queue listener."""

    _LOG_FMT = "{asctime} {levelname:7} {message}"
    _DEBUG_LOG_FMT = "{asctime} {levelname:7} {name:25} {message}"
    _DATEFMT = "%Y-%m-%d %H:%M:%S %Z"
    _FORMATTER_KWARGS = {"style": "{", "datefmt": _DATEFMT}
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
            formatter = logging.Formatter(fmt, **cls._FORMATTER_KWARGS)
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
            formatter = ColorFormatter(fmt, **cls._FORMATTER_KWARGS)
            handler.setFormatter(formatter)
        except Exception as exc:
            print("ERROR creating console logging handler", exc)
        return handler

    @classmethod
    def _get_log_handlers(cls):
        """Get handlers."""
        handlers = []
        if DEBUG:
            fmt = cls._DEBUG_LOG_FMT
        else:
            fmt = cls._LOG_FMT

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
