"""Purge comic covers."""

import os
import shutil
from abc import ABC
from pathlib import Path

from codex.librarian.covers.create import CoverCreateThread
from codex.librarian.covers.status import FindOrphanCoversStatus, RemoveCoversStatus
from codex.librarian.notifier.tasks import COVERS_CHANGED_TASK
from codex.models import Comic
from codex.models.paths import CustomCover


class CoverPurgeThread(CoverCreateThread, ABC):
    """Cover Purge methods."""

    _CLEANUP_STATUS_MAP = (FindOrphanCoversStatus, RemoveCoversStatus)

    @classmethod
    def _cleanup_cover_dirs(cls, path, cover_root):
        """Recursively remove empty cover directories."""
        if not path or cover_root not in path.parents:
            return
        try:
            path.rmdir()
            cls._cleanup_cover_dirs(path.parent, cover_root)
        except OSError:
            pass

    def purge_cover_paths(self, cover_paths, cover_root) -> int:
        """Purge a set a cover paths."""
        self.log.debug(f"Removing {len(cover_paths)} possible cover thumbnails...")
        status = RemoveCoversStatus(0, len(cover_paths))
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
                self.status_controller.update(status, notify=False)
            for cover_dir in cover_dirs:
                self._cleanup_cover_dirs(cover_dir, cover_root)
        finally:
            self.status_controller.finish(status)
        return status.complete or 0

    def purge_comic_covers(self, pks: frozenset[int], *, custom: bool):
        """Purge a set a cover paths."""
        cover_paths = self.get_cover_paths(pks, custom)
        cover_root = self.CUSTOM_COVERS_ROOT if custom else self.COVERS_ROOT
        return self.purge_cover_paths(cover_paths, cover_root)

    def purge_all_comic_covers(self, librarian_queue):
        """Purge every comic cover."""
        self.log.debug("Removing entire comic cover cache.")
        changed = False
        try:
            if self.COVERS_ROOT.exists():
                shutil.rmtree(self.COVERS_ROOT)
                changed = True
            if self.COVERS_ROOT.exists():
                shutil.rmtree(self.CUSTOM_COVERS_ROOT)
                changed = True
            self.log.success("Removed entire comic cover cache and custom cover cache.")
        except OSError as exc:
            self.log.warning(exc)
        if changed:
            librarian_queue.put(COVERS_CHANGED_TASK)

    def _cleanup_orphan_covers(self, cover_class, cover_root, name):
        """Remove all orphan cover thumbs."""
        status = FindOrphanCoversStatus()
        try:
            self.log.debug(f"Removing covers from missing {name}.")
            self.status_controller.start(status)
            pks = cover_class.objects.all().values_list("pk", flat=True)
            db_cover_paths = self.get_cover_paths(pks, custom=False)

            orphan_cover_paths = set()
            for root, _, filenames in os.walk(cover_root):
                root_path = Path(root)
                for fn in filenames:
                    fs_cover_path = root_path / fn
                    if fs_cover_path not in db_cover_paths:
                        orphan_cover_paths.add(fs_cover_path)
        finally:
            self.status_controller.finish(status)

        self.purge_cover_paths(orphan_cover_paths, cover_root)

    def cleanup_orphan_covers(self):
        """Cleanup both comic and custom covers."""
        self._cleanup_orphan_covers(Comic, self.COVERS_ROOT, "comics")
        self._cleanup_orphan_covers(
            CustomCover, self.CUSTOM_COVERS_ROOT, "custom covers"
        )
