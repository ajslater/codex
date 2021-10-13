"""Logging classes."""
import logging
import os

from logging.handlers import TimedRotatingFileHandler

from colors import color


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

    def __init__(self, format, *args, **kwargs):
        """Set up the FORMATS dict."""
        super().__init__(*args, **kwargs)
        for level_name, args in self.FORMAT_COLORS.items():
            levelno = getattr(logging, level_name)
            template = color(format, **args)
            formatter = logging.Formatter(template)
            self.FORMATTERS[levelno] = formatter

    def format(self, record):
        """Format each log message."""
        formatter = self.FORMATTERS[record.levelno]
        return formatter.format(record)


LOG_FMT = (
    "%(asctime)s %(processName)s %(threadName)s %(name)s %(levelname)s %(message)s"
)
LOG_FORMATTER = ColorFormatter(LOG_FMT)
LOG_CONSOLE_HANDLER = logging.StreamHandler()
LOG_CONSOLE_HANDLER.setFormatter(LOG_FORMATTER)


def get_file_log_handler(log_dir):
    """Get the log handlers for initialization."""
    log_dir.mkdir(exist_ok=True, parents=True)
    fn = log_dir / "codex.log"
    file_handler = TimedRotatingFileHandler(fn, when="D", backupCount=30)
    formatter = logging.Formatter(LOG_FMT)
    file_handler.setFormatter(formatter)
    return file_handler


def init_logging(log_dir, debug):
    """Initialize logging."""
    if debug:
        level = "DEBUG"
    else:
        level = os.environ.get("LOGLEVEL", "INFO").upper()
    log_file_handler = get_file_log_handler(log_dir)
    handlers = (LOG_CONSOLE_HANDLER, log_file_handler)
    logging.basicConfig(level=level, handlers=handlers)
