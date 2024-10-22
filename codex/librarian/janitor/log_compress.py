"""Rotate logs."""

from dataclasses import dataclass
from lzma import LZMAFile
from pathlib import Path

from humanize import naturalsize

from codex.librarian.janitor.status import JanitorStatusTypes
from codex.settings.settings import LOG_DIR
from codex.status import Status
from codex.worker_base import WorkerBaseMixin

_LOG_GLOB = "codex.log.*"


@dataclass
class LogStats:
    """Collect stats for compressed logs."""

    count = 0
    old_size = 0
    new_size = 0


class LogCompressMixin(WorkerBaseMixin):
    """Rotate logs with janitor."""

    @staticmethod
    def _get_old_log_paths():
        """Get old log paths to compress and sort them by reverse age."""
        old_log_paths = {}
        for path_str in LOG_DIR.glob(_LOG_GLOB):
            old_path = Path(path_str)
            try:
                log_number = int(old_path.suffix[1:])
                if log_number == 1:
                    continue
            except ValueError:
                continue
            old_log_paths[log_number] = old_path
        return dict(sorted(old_log_paths.items(), reverse=True)).values()

    @staticmethod
    def _rotate_log(old_path, stats):
        """Rotate one log file."""
        new_path = Path(str(old_path) + ".xz")
        if new_path.exists():
            return
        with (
            LZMAFile(new_path, mode="w", preset=9) as log_archive,
            old_path.open("r") as log_file,
        ):
            data = log_file.read()
            log_archive.write(data.encode())
        stats.count += 1
        stats.old_size += old_path.stat().st_size
        stats.new_size += new_path.stat().st_size
        if new_path.exists():
            old_path.unlink(missing_ok=True)

    def log_compress(self):
        """Compress old log files and report on savings."""
        status = Status(JanitorStatusTypes.COMPRESS_LOGS)
        try:
            self.status_controller.start(status)
            old_log_paths = self._get_old_log_paths()
            stats = LogStats()
            for old_path in old_log_paths:
                self._rotate_log(old_path, stats)
            if stats.count:
                saved = naturalsize(stats.old_size - stats.new_size)
                self.log.info(f"Compressed logs. Saved {saved}.")
            else:
                self.log.debug("No logs compressed.")
        finally:
            self.status_controller.finish(status)
