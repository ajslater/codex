"""Central Logging Thread."""
import logging

from logging.handlers import QueueListener, RotatingFileHandler

from colors import color

from codex.logger.log_queue import LOG_QUEUE
from codex.settings.logging import LOG_TO_CONSOLE, LOG_TO_FILE
from codex.settings.settings import LOG_DIR


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


class Logger(QueueListener):
    """Host for logging queue listener."""

    LOG_FMT = "{asctime} {levelname:8} {name} {message}"
    DATEFMT = "%Y-%m-%d %H:%M:%S %Z"
    FORMATTER_KWARGS = {"style": "{", "datefmt": DATEFMT}
    LOG_PATH = LOG_DIR / "codex.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024

    def __init__(self):
        """Start self with handlers."""
        handlers = self._get_log_handlers()
        super().__init__(LOG_QUEUE, *handlers)

    @classmethod
    def _get_file_log_handler(cls):
        """Get the log handlers for initialization."""
        handler = None
        try:
            cls.LOG_PATH.parent.mkdir(exist_ok=True, parents=True)
            handler = RotatingFileHandler(
                cls.LOG_PATH, maxBytes=cls.LOG_MAX_BYTES, backupCount=30
            )
            formatter = logging.Formatter(cls.LOG_FMT, **cls.FORMATTER_KWARGS)
            handler.setFormatter(formatter)
        except Exception as exc:
            print("ERROR getting file log handler", exc)
        return handler

    @classmethod
    def _get_console_handler(cls):
        """Create the console handler."""
        handler = None
        try:
            handler = logging.StreamHandler()
            formatter = ColorFormatter(cls.LOG_FMT, **cls.FORMATTER_KWARGS)
            handler.setFormatter(formatter)
        except Exception as exc:
            print("ERROR getting console log handler", exc)
        return handler

    @classmethod
    def _get_log_handlers(cls):
        """Get handlers."""
        handlers = []
        if LOG_TO_FILE:
            handlers.append(cls._get_file_log_handler())
        if LOG_TO_CONSOLE:
            handlers.append(cls._get_console_handler())
        return handlers
