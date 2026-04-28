"""Clean up the database after moves or imports."""

import os
from collections import defaultdict
from pathlib import Path
from types import MappingProxyType

from django.contrib.sessions.models import Session
from django.core import signing
from django.db import transaction
from django.db.models.functions.datetime import Now

from codex.librarian.scribe.janitor.failed_imports import JanitorUpdateFailedImports
from codex.librarian.scribe.janitor.status import (
    JanitorCleanupBookmarksStatus,
    JanitorCleanupCoversStatus,
    JanitorCleanupSessionsStatus,
    JanitorCleanupSettingsStatus,
    JanitorCleanupTagsStatus,
)
from codex.models import (
    AgeRating,
    Character,
    Country,
    Credit,
    CreditPerson,
    CreditRole,
    Folder,
    Genre,
    Identifier,
    IdentifierSource,
    Imprint,
    Language,
    Location,
    OriginalFormat,
    Publisher,
    ScanInfo,
    Series,
    SeriesGroup,
    Story,
    StoryArc,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
    Universe,
    Volume,
)
from codex.models.bookmark import Bookmark
from codex.models.paths import CustomCover
from codex.models.settings import SettingsBrowser, SettingsReader

_FK_MODELS = (
    Identifier,
    AgeRating,
    Country,
    CreditRole,
    CreditPerson,
    StoryArc,
    IdentifierSource,
    Credit,
    Character,
    Genre,
    Folder,
    Language,
    Location,
    Imprint,
    OriginalFormat,
    Publisher,
    Series,
    SeriesGroup,
    ScanInfo,
    StoryArcNumber,
    Story,
    Tagger,
    Tag,
    Team,
    Volume,
    Universe,
)
_TOTAL_NUM_FK_CLASSES = len(_FK_MODELS)


def _create_reverse_rel_map_for_model(model, rel_map) -> None:
    rev_rels = []
    filter_dict = {}
    for field in model._meta.get_fields():
        if not field.auto_created:
            continue
        if hasattr(field, "get_accessor_name") and (an := field.get_accessor_name()):
            rel = an
        elif field.name:
            rel = field.name
        else:
            continue
        if rel == "id":
            continue
        rel = rel.removesuffix("_set")
        rev_rels.append(rel)
        filter_dict[f"{rel}__isnull"] = True
    if filter_dict:
        rel_map[model] = filter_dict


def _create_reverse_rel_map() -> MappingProxyType:
    rel_map = {}
    for model in _FK_MODELS:
        _create_reverse_rel_map_for_model(model, rel_map)
    return MappingProxyType(rel_map)


_MODEL_REVERSE_EMPTY_FILTER_MAP = _create_reverse_rel_map()
_BOOKMARK_FILTER = dict.fromkeys(
    (f"{rel}__isnull" for rel in ("session", "user", "comic")), True
)
_SETTINGS_ORPHAN_FILTER = dict.fromkeys(
    (f"{rel}__isnull" for rel in ("session", "user")), True
)
# Iteration cap on ``cleanup_fks``'s convergence loop. Codex's FK graph
# depth is bounded by the hierarchy
# Identifier -> Publisher -> Imprint -> Series -> Volume -> Comic
# plus the per-tag join branches; a fully-orphaned chain converges in
# at most ~5 passes regardless of deletion order. 10 doubles that for
# safety. If a real DB ever fails to converge in 10 passes that's a
# data-integrity bug worth investigating, not a fix-by-bumping-the-cap
# problem.
_FK_CLEANUP_MAX_PASSES = 10


class JanitorCleanup(JanitorUpdateFailedImports):
    """Cleanup methods for Janitor."""

    def _cleanup_fks_model(self, model, filter_dict, status):
        status.subtitle = model._meta.verbose_name_plural
        self.status_controller.update(status)
        qs = model.objects.filter(**filter_dict).distinct()
        count, _ = qs.delete()
        status.complete += count
        self.status_controller.update(status)
        return count

    def _cleanup_fks_one_level(self, status) -> int:
        count = 0
        for model, filter_dict in _MODEL_REVERSE_EMPTY_FILTER_MAP.items():
            if self.abort_event.is_set():
                return count
            count += self._cleanup_fks_model(model, filter_dict, status)
        return count

    def cleanup_fks(self) -> None:
        """
        Clean up unused foreign keys.

        Walks every FK model and deletes rows with no inbound references.
        Cascading deletes can produce more orphans (a Credit's deletion
        leaves CreditPerson / CreditRole orphan), so the loop runs until
        the per-pass count converges to zero or the cap is hit.

        Wrapped in ``transaction.atomic`` so the multi-pass convergence
        is all-or-nothing: an exception mid-pass rolls back to pre-
        cleanup state rather than leaving a partially-cleaned graph.
        The 25 per-model deletes also coalesce into one fsync.
        """
        self.abort_event.clear()
        status = JanitorCleanupTagsStatus(0)
        try:
            self.status_controller.start(status)
            self.log.debug("Cleaning up orphan tags...")
            # Hold ``db_write_lock`` across all passes so a concurrent
            # importer can't re-introduce a parent FK between the
            # check that found it orphaned and the DELETE that removes
            # it. The integrity-check writers in ``integrity/`` use the
            # same pattern; cleanup was previously missing it.
            converged = False
            with self.db_write_lock, transaction.atomic():
                for _ in range(_FK_CLEANUP_MAX_PASSES):
                    if self.abort_event.is_set():
                        return
                    count = self._cleanup_fks_one_level(status)
                    if not count:
                        converged = True
                        break
            if not converged and not self.abort_event.is_set():
                cap = _FK_CLEANUP_MAX_PASSES
                self.log.warning(
                    f"FK cleanup hit {cap}-pass cap without converging — investigate the reverse-relation map or the data graph."
                )
            level = "INFO" if status.complete else "DEBUG"
            self.log.log(level, f"Cleaned up {status.complete} unused tags.")
        finally:
            if self.abort_event.is_set():
                self.log.info("Cleanup tags task aborted early.")
            self.abort_event.clear()
            self.status_controller.finish(status)

    @staticmethod
    def _group_covers_by_parent(covers) -> dict[str, list[tuple[int, str]]]:
        """
        Bunch (pk, basename) entries by parent directory.

        Cover layouts are typically one-cover-per-series-folder, so
        each parent ends up with one entry. For installs that share a
        directory across many covers, this groups them so the parent
        gets one ``scandir`` instead of N ``stat`` calls.
        """
        by_dir: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for cover in covers:
            cover_path = Path(cover.path)
            by_dir[str(cover_path.parent)].append((cover.pk, cover_path.name))
        return by_dir

    @staticmethod
    def _scan_parent_for_present_names(parent: str) -> frozenset[str] | None:
        """
        Return the set of filenames in ``parent``, or None on read failure.

        ``None`` is the "fall back to per-file ``Path.exists()``" signal;
        callers handle it by treating each cover in the group as
        unverified rather than guessing at orphan-vs-present.
        """
        try:
            with os.scandir(parent) as it:
                return frozenset(entry.name for entry in it)
        except FileNotFoundError:
            # Parent directory itself is gone — every cover claiming a
            # path under it is orphan. Empty set is correct.
            return frozenset()
        except OSError:
            # Permission error, transient FS hiccup, etc. — fall back.
            return None

    def _collect_orphan_cover_pks(
        self, by_dir: dict[str, list[tuple[int, str]]], status
    ) -> list[int]:
        """Walk parent directories once via scandir and flag orphans."""
        delete_pks: list[int] = []
        for parent, entries in by_dir.items():
            present = self._scan_parent_for_present_names(parent)
            for pk, basename in entries:
                if present is None:
                    # scandir failed for this parent; preserve
                    # pre-fix behavior with a per-file Path.exists().
                    if not Path(parent, basename).exists():
                        delete_pks.append(pk)
                elif basename not in present:
                    delete_pks.append(pk)
                status.increment_complete()
            self.status_controller.update(status)
        return delete_pks

    def cleanup_custom_covers(self) -> None:
        """
        Clean up unused custom covers.

        Replaces the prior per-cover ``Path.exists()`` loop with a
        directory-grouped ``os.scandir`` pass. For typical cover
        layouts one parent ↔ one cover, the wall-clock is identical;
        for any layout with multiple covers per parent (or for
        many covers under sibling directories), the parent's
        ``readdir`` round-trip replaces N individual ``stat``
        round-trips. Big win on NFS / SMB / cloud-mounted media
        where each ``stat`` is single-digit milliseconds.
        """
        # Materialize once so we can group by parent directory before
        # the FS pass. ``only`` keeps the load lean.
        covers = list(CustomCover.objects.only("pk", "path"))
        status = JanitorCleanupCoversStatus(0, len(covers))
        try:
            self.status_controller.start(status)
            self.log.debug("Cleaning up db custom covers with no source images...")
            by_dir = self._group_covers_by_parent(covers)
            # Read-only phase: lock not held — importer can keep writing
            # while we walk slow storage.
            delete_pks = self._collect_orphan_cover_pks(by_dir, status)
            # Write phase under the lock so a concurrent importer can't
            # be mid-bulk_create on the same rows. TOCTOU window is
            # acceptable: a cover re-created between scan and delete
            # just gets re-discovered next poll.
            with self.db_write_lock:
                delete_qs = CustomCover.objects.filter(pk__in=delete_pks)
                count, _ = delete_qs.delete()
                status.complete = count
        finally:
            self.status_controller.finish(status)

    def cleanup_sessions(self) -> None:
        """Delete expired and corrupt sessions."""
        status = JanitorCleanupSessionsStatus()
        try:
            self.status_controller.start(status)
            # Expired-session DELETE under the lock.
            with self.db_write_lock:
                qs = Session.objects.filter(expire_date__lt=Now())
                count, _ = qs.delete()
            if count:
                self.log.info(f"Deleted {count} expired sessions.")
            # Read-only signature validation phase. Holding the lock
            # across this loop would block the importer for as long as
            # the validation takes; release between the two phases.
            bad_session_keys = set()
            store = Session.get_session_store_class()()
            salt = store.key_salt  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            serializer = store.serializer
            for encoded_session in Session.objects.all():
                # Session.get_decoded() swallows decode errors and returns
                # an empty dict, which is also the legitimate state for an
                # anonymous session with no stored data — so we can't use
                # it to detect corruption. Call signing.loads directly so a
                # genuine signature/decode failure raises.
                try:
                    signing.loads(
                        encoded_session.session_data,
                        salt=salt,
                        serializer=serializer,
                    )
                except Exception:
                    bad_session_keys.add(encoded_session.session_key)

            if bad_session_keys:
                with self.db_write_lock:
                    bad_sessions = Session.objects.filter(
                        session_key__in=bad_session_keys
                    )
                    count, _ = bad_sessions.delete()
                self.log.info(f"Deleted {count} corrupt sessions.")
        finally:
            self.status_controller.finish(status)

    def cleanup_orphan_bookmarks(self) -> None:
        """Delete bookmarks without users or sessions."""
        status = JanitorCleanupBookmarksStatus()
        try:
            self.status_controller.start(status)
            with self.db_write_lock:
                orphan_bms = Bookmark.objects.filter(**_BOOKMARK_FILTER)
                count, _ = orphan_bms.delete()
            level = "INFO" if count else "DEBUG"
            self.log.log(level, f"Deleted {count} orphan bookmarks.")
        finally:
            self.status_controller.finish(status)

    def cleanup_orphan_settings(self) -> None:
        """Delete settings rows without both a user and a session."""
        status = JanitorCleanupSettingsStatus()
        try:
            self.status_controller.start(status)
            total = 0
            with self.db_write_lock:
                for model in (SettingsBrowser, SettingsReader):
                    orphans = model.objects.filter(**_SETTINGS_ORPHAN_FILTER)
                    count, _ = orphans.delete()
                    total += count
            level = "INFO" if total else "DEBUG"
            self.log.log(level, f"Deleted {total} orphan settings rows.")
        finally:
            self.status_controller.finish(status)
