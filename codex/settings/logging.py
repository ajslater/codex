"""Logging classes."""
import logging
import os

from logging.handlers import TimedRotatingFileHandler

from colors import color


# "{asctime} {processName} {threadName} {name} {levelname} {message}"
LOG_FMT = "{asctime} {levelname:8} {message}"
DATEFMT = "%Y-%m-%d %H:%M:%S %Z"
VERBOSE = int((logging.INFO + logging.DEBUG) / 2)
LOG_EVERY = 15


def _verbose(self, message, *args, **kwargs):
    """Verbose logging level function."""
    if self.isEnabledFor(logging.VERBOSE):  # type: ignore
        self._log(logging.VERBOSE, message, args, **kwargs)  # type: ignore


def _add_verbose_logging_level():
    """Add the verbose logging level to the main Logger."""
    logging.VERBOSE = VERBOSE  # type: ignore
    logging.addLevelName(logging.VERBOSE, "VERBOSE")  # type: ignore
    logging.Logger.verbose = _verbose  # type: ignore


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


def _get_file_log_handler(log_dir):
    """Get the log handlers for initialization."""
    log_dir.mkdir(exist_ok=True, parents=True)
    fn = log_dir / "codex.log"
    file_handler = TimedRotatingFileHandler(fn, when="D", backupCount=30)
    formatter = logging.Formatter(LOG_FMT, style="{", datefmt=DATEFMT)
    file_handler.setFormatter(formatter)
    return file_handler


def _get_log_level(debug):
    """Get the log level."""
    environ_loglevel = os.environ.get("LOGLEVEL")
    if environ_loglevel:
        level = environ_loglevel
    elif debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    return level


def _get_log_handlers(log_dir):
    """Get handlers."""
    log_file_handler = _get_file_log_handler(log_dir)
    log_console_handler = logging.StreamHandler()
    log_formatter = ColorFormatter(LOG_FMT, style="{", datefmt=DATEFMT)
    log_console_handler.setFormatter(log_formatter)
    return (log_console_handler, log_file_handler)


def init_logging(log_dir, debug):
    """Initialize logging."""
    _add_verbose_logging_level()
    level = _get_log_level(debug)
    handlers = _get_log_handlers(log_dir)
    logging.basicConfig(level=level, handlers=handlers)
