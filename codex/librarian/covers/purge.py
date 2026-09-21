"""Purge comic covers."""

import shutil
from abc import ABC
from pathlib import Path

from codex.librarian.covers.create import CoverCreateThread
from codex.librarian.covers.status import FindOrphanCoversStatus, RemoveCoversStatus
from codex.librarian.notifier.tasks import COVERS_CHANGED_TASK


class CoverPurgeThread(CoverCreateThread, ABC):
    """Cover Purge methods."""

    _CLEANUP_STATUS_MAP = (FindOrphanCoversStatus, RemoveCoversStatus)

    @classmethod
    def _cleanup_cover_dirs(cls, path, cover_root) -> None:
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

    def purge_comic_covers(self, pks: frozenset[int], *, custom: bool) -> int:
        """Purge a set a cover paths."""
        cover_paths = self.get_cover_paths(pks, custom=custom)
        cover_root = self.get_cover_root(custom=custom)
        return self.purge_cover_paths(cover_paths, cover_root)

    def purge_all_comic_covers(self, librarian_queue) -> None:
        """Purge every comic cover."""
        self.log.debug("Removing entire comic cover cache.")
        status = RemoveCoversStatus()
        try:
            self.status_controller.start(status)
            if self.COVERS_ROOT.exists():
                shutil.rmtree(self.COVERS_ROOT)
            if self.CUSTOM_COVERS_ROOT.exists():
                shutil.rmtree(self.CUSTOM_COVERS_ROOT)
            self.log.success("Removed entire comic cover cache and custom cover cache.")
        except OSError as exc:
            self.log.warning(exc)
        finally:
            self.status_controller.finish(status)
        # Whole-cache purge: clients drop every cached cover.
        librarian_queue.put(COVERS_CHANGED_TASK)

    def _cleanup_orphan_covers(self, *, custom: bool) -> None:
        """
        Remove all orphan cover thumbs for one cover namespace.

        Every namespace-dependent value comes from the one ``custom``
        flag. They were three arguments that had to agree, and the db
        path set was built for the comic namespace no matter which root
        was being walked -- so every custom thumb looked like an orphan.
        """
        cover_root = self.get_cover_root(custom=custom)
        desc = self.get_cover_desc(custom=custom)
        status = FindOrphanCoversStatus()
        try:
            self.log.debug(f"Removing orphan {desc} covers.")
            self.status_controller.start(status)
            cover_class = self.get_cover_model(custom=custom)
            pks = cover_class.objects.all().values_list("pk", flat=True)
            db_cover_paths = self.get_cover_paths(pks, custom=custom)

            orphan_cover_paths = set()
            # No ``on_error=``: the default silently skips a directory
            # that will not list, and skipped means not deleted. Here
            # that silence is the fail-safe direction.
            for root, _, filenames in cover_root.walk():
                root_path = Path(root)
                for fn in filenames:
                    fs_cover_path = root_path / fn
                    if fs_cover_path not in db_cover_paths:
                        orphan_cover_paths.add(fs_cover_path)
        finally:
            self.status_controller.finish(status)

        self.purge_cover_paths(orphan_cover_paths, cover_root)

    def _cleanup_tmp_covers(self) -> None:
        """Remove stale ``*.tmp`` files left behind by aborted atomic writes."""
        for cover_root in (self.COVERS_ROOT, self.CUSTOM_COVERS_ROOT):
            if not cover_root.exists():
                continue
            for tmp_path in cover_root.rglob("*.tmp"):
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    self.log.warning(f"Could not remove stale {tmp_path}: {exc!r}")

    def cleanup_orphan_covers(self) -> None:
        """Cleanup both comic and custom covers."""
        self._cleanup_tmp_covers()
        for custom in (False, True):
            self._cleanup_orphan_covers(custom=custom)
