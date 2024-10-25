"""Central Logging Thread."""

import logging
import shutil
from logging.handlers import QueueListener, RotatingFileHandler
from lzma import LZMAFile
from pathlib import Path

from codex.logger.formatter import ColorFormatter
from codex.settings.settings import DEBUG, LOG_DIR, LOG_TO_CONSOLE, LOG_TO_FILE

_LOG_FMT = "{asctime} {levelname:7} {message}"
_DEBUG_LOG_FMT = "{asctime} {levelname:7} {name:25} {message}"
_DATEFMT = "%Y-%m-%d %H:%M:%S %Z"
_FORMATTER_STYLE = "{"
_LOG_PATH = LOG_DIR / "codex.log"
_LOG_MAX_BYTES = 10 * 2**20  # 10 MiB
_LOG_BACKUP_COUNT = 30


class RotatingXZFileHandler(RotatingFileHandler):
    """Rotating File Handler rotates into XZ."""

    @staticmethod
    def namer(name):
        """Name files with xz."""
        return name + ".xz"

    @staticmethod
    def rotator(source, dest):
        """Compress File."""
        source_path = Path(source)
        with (
            source_path.open("rb") as f_in,
            LZMAFile(dest, mode="wb", preset=9) as f_out,
        ):
            shutil.copyfileobj(f_in, f_out)
        source_path.unlink()


class CodexLogQueueListener(QueueListener):
    """Host for logging queue listener."""

    @classmethod
    def _get_file_log_handler(cls, fmt):
        """Get the log handlers for initialization."""
        handler = None
        try:
            _LOG_PATH.parent.mkdir(exist_ok=True, parents=True)
            handler = RotatingXZFileHandler(
                _LOG_PATH,
                maxBytes=_LOG_MAX_BYTES,
                backupCount=_LOG_BACKUP_COUNT,
                delay=True,
            )
            formatter = logging.Formatter(fmt, style=_FORMATTER_STYLE, datefmt=_DATEFMT)
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
            formatter = ColorFormatter(fmt, style=_FORMATTER_STYLE, datefmt=_DATEFMT)
            handler.setFormatter(formatter)
        except Exception as exc:
            print("ERROR creating console logging handler", exc)
        return handler

    @classmethod
    def _get_log_handlers(cls):
        """Get handlers."""
        handlers = []
        fmt = _DEBUG_LOG_FMT if DEBUG else _LOG_FMT

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
