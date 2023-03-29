"""Purge comic covers."""
import os
import shutil
from pathlib import Path

from codex.librarian.covers.path import CoverPathMixin
from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.notifier.tasks import LIBRARY_CHANGED_TASK
from codex.models import Comic, Timestamp
from codex.status import Status


class CoverPurgeMixin(CoverPathMixin):
    """Cover Purge methods."""

    _CLEANUP_STATUS_MAP = (
        Status(CoverStatusTypes.FIND_ORPHAN),
        Status(CoverStatusTypes.PURGE_COVERS),
    )

    @classmethod
    def _cleanup_cover_dirs(cls, path):
        """Recursively remove empty cover directories."""
        if not path or cls.COVER_ROOT not in path.parents:
            return
        try:
            path.rmdir()
            cls._cleanup_cover_dirs(path.parent)
        except OSError:
            pass

    def purge_cover_paths(self, cover_paths):
        """Purge a set a cover paths."""
        self.log.debug(f"Removing {len(cover_paths)} possible cover thumbnails...")
        status = Status(CoverStatusTypes.PURGE_COVERS, 0, len(cover_paths))
        try:
            self.status_controller.start(status)
            cover_dirs = set()
            for cover_path in cover_paths:
                try:
                    cover_path.unlink()
                    status.increment_complete()
                except FileNotFoundError:
                    status.decrement_total()
                cover_dirs.add(cover_path.parent)
                self.status_controller.update(status)
            for cover_dir in cover_dirs:
                self._cleanup_cover_dirs(cover_dir)
            self.log.info(f"Removed {status.complete} cover thumbnails.")
        finally:
            self.status_controller.finish(status)
        return status.complete

    def purge_comic_covers(self, comic_pks):
        """Purge a set a cover paths."""
        cover_paths = self.get_cover_paths(comic_pks)
        return self.purge_cover_paths(cover_paths)

    def purge_all_comic_covers(self, librarian_queue):
        """Purge every comic cover."""
        self.log.debug("Removing entire comic cover cache.")
        try:
            shutil.rmtree(self.COVER_ROOT)
            self.log.info("Removed entire comic cover cache.")
        except Exception as exc:
            self.log.warning(exc)
        Timestamp.touch(Timestamp.TimestampChoices.COVERS)
        librarian_queue.put(LIBRARY_CHANGED_TASK)

    def cleanup_orphan_covers(self):
        """Remove all orphan cover thumbs."""
        try:
            self.log.debug("Removing covers from missing comics.")
            self.status_controller.start_many(self._CLEANUP_STATUS_MAP)
            comic_pks = Comic.objects.all().values_list("pk", flat=True)
            db_cover_paths = self.get_cover_paths(comic_pks)

            orphan_cover_paths = set()
            for root, _, filenames in os.walk(self.COVER_ROOT):
                root_path = Path(root)
                for fn in filenames:
                    fs_cover_path = root_path / fn
                    if fs_cover_path not in db_cover_paths:
                        orphan_cover_paths.add(fs_cover_path)
        finally:
            self.status_controller.finish(CoverStatusTypes.FIND_ORPHAN)

        count = self.purge_cover_paths(orphan_cover_paths)
        self.log.info(f"Removed {count} covers for missing comics.")
        return count
