"""Central Logging Thread."""
import logging

from logging.handlers import QueueListener, RotatingFileHandler

from colors import color

from codex.logger.log_queue import LOG_QUEUE
from codex.settings.settings import LOG_DIR, LOG_TO_CONSOLE, LOG_TO_FILE


class ColorFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors."""

    FORMAT_COLORS = {
        "CRITICAL": {"fg": "red", "style": "bold"},
        "ERROR": {"fg": "red"},
        "WARNING": {"fg": "yellow"},
        "INFO": {"fg": "green"},
        "VERBOSE": {"fg": "cyan"},
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


class Logger:
    """Host for logging queue listener."""

    LOG_FMT = "{asctime} {levelname:8} {message}"
    DATEFMT = "%Y-%m-%d %H:%M:%S %Z"
    FORMATTER_KWARGS = {"style": "{", "datefmt": DATEFMT}
    LOG_PATH = LOG_DIR / "codex.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024

    @classmethod
    def _get_file_log_handler(cls):
        """Get the log handlers for initialization."""
        LOG_DIR.mkdir(exist_ok=True, parents=True)
        file_handler = RotatingFileHandler(
            cls.LOG_PATH, maxBytes=cls.LOG_MAX_BYTES, backupCount=30
        )
        formatter = logging.Formatter(cls.LOG_FMT, **cls.FORMATTER_KWARGS)
        file_handler.setFormatter(formatter)
        return file_handler

    @classmethod
    def _get_console_handler(cls):
        """Create the console handler."""
        log_console_handler = logging.StreamHandler()
        log_formatter = ColorFormatter(cls.LOG_FMT, **cls.FORMATTER_KWARGS)
        log_console_handler.setFormatter(log_formatter)
        return log_console_handler

    @classmethod
    def _get_log_handlers(cls):
        """Get handlers."""
        handlers = []
        if LOG_TO_FILE:
            handlers.append(cls._get_file_log_handler())
        if LOG_TO_CONSOLE:
            handlers.append(cls._get_console_handler())
        return handlers

    @classmethod
    def startup(cls):
        """Create handlers, listener and start."""
        handlers = cls._get_log_handlers()
        cls._listener = QueueListener(LOG_QUEUE, *handlers)
        cls._listener.start()

    @classmethod
    def shutdown(cls):
        """Stop listener."""
        cls._listener.stop()
