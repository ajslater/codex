"""
Clear the pending-delete stamp from paths a scan just observed.

A row whose file vanished is kept for a retention window instead of
being deleted, so its bookmarks survive a filesystem outage. Something
has to notice when the file comes back, and the importer will never do
it on its own: ``missing_since`` is excluded from
``BULK_UPDATE_COMIC_FIELDS`` and absent from ``BULK_UPDATE_FOLDER_FIELDS``
precisely so an unrelated re-import cannot clear a live stamp. A
returning file therefore gets its row updated in place -- pk and
bookmarks intact -- and stays stamped, stays invisible, and is reaped a
day later with the file sitting right there on disk.

The poller has its own answer (``_unstamp_revived``): it re-walks the
whole library every pass and intersects the stamped set with what is on
disk. That catches the case with no filesystem event at all -- a remount
where the stat never moved -- for which no import is ever queued, so no
hook here could see it. The two passes are complementary and neither
subsumes the other. What they share is the tail: ``clear_stamps`` and
``publish_revival``, which live in :mod:`codex.librarian.pending_deletes`
so the poller's revival, the admin's and this one cannot drift.

Two things this phase must get right, both of which look like details
and are not:

* **It keys off the task's paths, not off what the import decided to
  do.** ``_fs_stat_unchanged`` skips a path whose on-disk stat matches
  the stored one, which is exactly what a file restored from a backup
  or remounted looks like. Reading the revival off ``CREATE_COMICS``
  would miss the commonest case entirely.
* **It probes the disk.** A task naming a path is not evidence the path
  exists. ``ForceUpdater`` and ``LazyImporter`` build ``files_modified``
  from a database query, so both happily name a stamped comic whose file
  is still gone; without the probe, an admin pressing Force Update would
  un-hide every pending delete in the library and stop its countdown,
  and on a watched-but-unpolled library nothing would ever re-stamp
  them. The probe is what turns "a task mentioned this path" into "a
  scanner observed this path", which is the only claim that justifies
  clearing a stamp.
"""

from collections.abc import Collection, Mapping

from codex.librarian.pending_deletes import clear_stamps
from codex.librarian.scribe.importer.delete.existence import split_extant
from codex.librarian.scribe.importer.read import ReadMetadataImporter
from codex.models import Comic, Folder
from codex.settings import IMPORTER_LINK_FK_BATCH_SIZE


class ReviveImporter(ReadMetadataImporter):
    """Clear pending-delete stamps for paths this task observed."""

    def _observed_paths(self) -> dict[str, str]:
        """
        Map every path this task claims exists to the path to probe.

        The keys are **database** paths and the values are the disk
        paths that would prove them. For a move the two differ and the
        direction matters: this phase runs before
        ``move_and_modify_dirs``, so the row still sits at the *source*
        path while the evidence is at the destination. Keying on the
        destination would match nothing at all.
        """
        task = self.task
        # Paths that stand for themselves: the task claims they exist.
        candidates: dict[str, str] = {
            path: path
            for path in (
                *task.files_created,
                *task.files_modified,
                *task.dirs_modified,
            )
        }
        # Both ends of every move map to the destination, which is where
        # the evidence is.
        for moved in (task.files_moved, task.dirs_moved):
            candidates.update(
                (path, dest)
                for source, dest in moved.items()
                for path in (source, dest)
            )
        return candidates

    @staticmethod
    def _stamped_rows(model, library) -> dict[str, int]:
        """
        Every stamped path in this library, as ``{path: pk}``.

        Queried in this direction on purpose. The alternative --
        ``path__in=<every path the task names>`` -- would bind one SQL
        variable per path and need batching against SQLite's 32766-
        variable cap on exactly the imports that are already the
        largest. This way the filter is the partial index on
        ``missing_since``, which on a healthy library matches nothing,
        so the whole phase costs two indexed queries and stops. The
        admin view and the reaper fetch the same set unbatched.
        """
        return dict(
            model.objects.filter(
                library=library, missing_since__isnull=False
            ).values_list("path", "pk")
        )

    def _revive_folders(
        self, comic_paths: Collection[str], stamped: Mapping[str, int]
    ) -> dict[str, int]:
        """
        Add the ancestor folders of revived comics to the revival set.

        A returning directory produces no directory event of its own:
        the watcher expands an added dir into per-file adds only, so a
        restored subtree arrives as ``files_created`` and nothing else.
        Its Folder rows would keep their stamps forever -- and a stamped
        Folder is hidden by the ACL's *self* clause even when every
        comic beneath it is live, so the whole subtree would stay
        invisible while the reaper spared it for having live children.

        ``get_all_library_relative_paths`` is the importer's existing
        ancestor walk, already shared with the moved-comics path.

        A stamped leaf directory with no comics anywhere beneath it is
        not reachable this way, and deliberately so: nothing in a
        file-only task is evidence about it. The reaper takes it when
        the window expires, which is the right outcome for an empty
        directory nobody restored.
        """
        if not comic_paths:
            return {}
        ancestors = self.get_all_library_relative_paths(tuple(comic_paths))
        return {path: stamped[path] for (path,) in ancestors if path in stamped}

    def _candidate_revivals(
        self, candidates: Mapping[str, str]
    ) -> dict[type, dict[str, int]] | None:
        """
        Stamped rows this task names, plus the ancestors of its comics.

        Returns ``None`` when nothing in the library is being held at
        all, which is the overwhelmingly common case and the one worth
        leaving early for.
        """
        stamped = {
            model: self._stamped_rows(model, self.library) for model in (Comic, Folder)
        }
        if not any(stamped.values()):
            return None
        revived: dict[type, dict[str, int]] = {
            model: {path: pk for path, pk in rows.items() if path in candidates}
            for model, rows in stamped.items()
        }
        revived[Folder] |= self._revive_folders(revived[Comic], stamped[Folder])
        return revived

    @staticmethod
    def _keep_only_extant(
        revived: Mapping[type, dict[str, int]], candidates: Mapping[str, str]
    ) -> None:
        """
        Drop every candidate whose disk path is not really there.

        One probe over the whole (tiny) set, in place. ``split_extant``
        fails open in the direction wanted here: an unreadable path
        lands in ``extant``, so a row whose file is present but
        unreadable revives rather than staying stamped -- "I could not
        look" is not "it is not there".
        """
        probe = {
            candidates.get(path, path) for named in revived.values() for path in named
        }
        _gone, extant = split_extant(probe)
        on_disk = frozenset(extant)
        for named in revived.values():
            for path in tuple(named):
                if candidates.get(path, path) not in on_disk:
                    del named[path]

    def _clear(self, model, revived: Mapping[str, int]) -> int:
        """Clear stamps in batches, returning how many rows moved."""
        paths = tuple(revived)
        count = 0
        for start in range(0, len(paths), IMPORTER_LINK_FK_BATCH_SIZE):
            if self.abort_event.is_set():
                break
            batch = paths[start : start + IMPORTER_LINK_FK_BATCH_SIZE]
            # ``library=`` even though the pks are already scoped: every
            # path lookup in the importer ANDs it in, so the
            # overlapping-libraries audit stays one grep.
            count += clear_stamps(model, library=self.library, path__in=batch)
        return count

    def unstamp_revived(self) -> None:
        """
        Clear the stamp from every observed path that is really on disk.

        Runs as its own pre-phase rather than inside ``init_apply``: it
        must land after ``start_time`` is set, because the delete
        phase's ``update_library_collections`` re-stamps a collection
        whose comic's ``updated_at`` moved since then -- which is how a
        revived comic's parent collections get their browser refresh for
        free -- and before ``move_and_modify_dirs``, which rewrites
        ``Folder.path`` and would invalidate the source-path keying.

        Carries no :class:`Status` of its own. A status code is a
        persisted model choice, so a new one costs a migration, and this
        phase is a no-op on every healthy import -- two indexed queries
        against a partial index that matches nothing. ``timed_step``
        still records it in the finish-time phase table.
        """
        candidates = self._observed_paths()
        if not candidates:
            return
        revived = self._candidate_revivals(candidates)
        if revived is None:
            return
        self._keep_only_extant(revived, candidates)

        comics = self._clear(Comic, revived[Comic])
        folders = self._clear(Folder, revived[Folder])
        self.revived_comic_pks |= set(revived[Comic].values())
        self.counts.comics_revived += comics
        self.counts.folders_revived += folders
        if comics or folders:
            reason = (
                f"{comics} comics and {folders} folders came back in"
                f" {self.library.path}."
            )
            self.log.info(reason)
