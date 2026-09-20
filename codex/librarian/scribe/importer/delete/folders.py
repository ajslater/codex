"""Delete database folders methods."""

import os

from django.db.models import Q

from codex.librarian.scribe.importer.delete.comics import DeletedComicsImporter
from codex.librarian.scribe.importer.delete.existence import (
    confirm_deleted,
    split_extant,
)
from codex.librarian.scribe.importer.statii.delete import ImporterRemoveFoldersStatus
from codex.models.collections import Folder
from codex.models.comic import Comic


class DeletedFoldersImporter(DeletedComicsImporter):
    """Delete database folders methods."""

    def _cascade_comic_qs(self, folders):
        """
        Return every comic a folder delete takes with it.

        The destructive edge is ``Comic.parent_folder``, which cascades;
        the ``folders`` m2m is the one the collection bookkeeping reads
        and can drift from it. Union both so nothing is deleted without
        being counted, re-stamped and existence-checked.
        """
        return Comic.objects.filter(
            Q(parent_folder__in=folders) | Q(folders__in=folders),
            library=self.library,
        ).distinct()

    def _confirm_cascade(self, paths: tuple[str, ...]) -> tuple[str, ...]:
        """
        Drop folder deletes whose comics are still on disk.

        ``confirm_deleted`` probes the folder paths, but the comics under
        them die by cascade without a probe of their own — one folder
        that failed to answer used to destroy every comic beneath it and
        their bookmarks. This runs after the delete phase's second look,
        so it is already a late probe: a comic that revived during the
        wait keeps its folder here. On a coherent filesystem a folder that answers
        ENOENT cannot have children that answer anything else, so this
        is a backstop for the case that motivates the whole module: a
        network share whose answers disagree with each other.

        A comic is saved by dropping every folder above it, not just its
        parent: ``Folder.parent_folder`` cascades too, so an ancestor
        left in the delete set would take the child folder and the comic
        with it anyway.
        """
        folders = Folder.objects.filter(library=self.library, path__in=paths)
        comic_paths = tuple(
            self._cascade_comic_qs(folders).values_list("path", flat=True)
        )
        if not comic_paths:
            return paths
        _gone, extant = split_extant(comic_paths)
        if not extant:
            return paths
        prefixes = tuple(path.rstrip(os.sep) + os.sep for path in paths)
        kept_prefixes = {
            prefix for prefix in prefixes if any(p.startswith(prefix) for p in extant)
        }
        trimmed = tuple(
            path for path in paths if path.rstrip(os.sep) + os.sep not in kept_prefixes
        )
        reason = (
            f"Not deleting {len(paths) - len(trimmed)} folders that still"
            f" hold {len(extant)} comics on disk."
        )
        self.log.warning(reason)
        return trimmed

    def bulk_folders_deleted(self, **kwargs) -> tuple[int, int, dict]:
        """
        Bulk delete folders. Return (folders, cascaded comics, collections).

        Comics under a deleted folder die by the ``parent_folder`` cascade
        rather than through ``bulk_comics_deleted``, so their collections
        are gathered here too. Without them a series or publisher emptied by
        a folder delete is never re-stamped, and browsers viewing it keep
        listing comics that are gone until some unrelated import moves the
        timestamp.
        """
        status = ImporterRemoveFoldersStatus(0, len(self.task.dirs_deleted))
        deleted_comic_collections = self._init_deleted_comic_collections()
        try:
            if not self.task.dirs_deleted:
                return 0, 0, deleted_comic_collections
            self.status_controller.start(status)
            paths = confirm_deleted(self.task.dirs_deleted, self.log, "folders")
            self.task.dirs_deleted = frozenset()
            if paths:
                paths = self._confirm_cascade(paths)
            if not paths:
                return 0, 0, deleted_comic_collections
            folders = Folder.objects.filter(library=self.library, path__in=paths)
            folder_count = folders.count()
            delete_comic_qs = self._cascade_comic_qs(folders)
            self._populate_deleted_comic_collections(
                delete_comic_qs, deleted_comic_collections
            )
            delete_comic_pks = frozenset(delete_comic_qs.values_list("pk", flat=True))
            # The cascade is the only destructive path that never names
            # the comics it removes. Say so before it runs, every time,
            # so a user asking where their comics went has a breadcrumb.
            if delete_comic_pks:
                reason = (
                    f"Deleting {len(delete_comic_pks)} comics under"
                    f" {folder_count} deleted folders in {self.library.path}."
                )
                self.log.info(reason)
            self._warn_on_mass_delete(len(delete_comic_pks))
            folders.delete()

            self.remove_covers(delete_comic_pks, custom=False)
        finally:
            self.status_controller.finish(status)
        return folder_count, len(delete_comic_pks), deleted_comic_collections
