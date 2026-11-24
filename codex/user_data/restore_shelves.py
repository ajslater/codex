"""
Restore an older backup's shelves and favorites as personal reading lists.

Split out of :mod:`codex.user_data.restore`. Shelves folded into reading
lists, so new backups carry no ``shelves`` or ``shelf_items`` table; a
backup written before then does, and one written before shelves existed
carries ``favorites`` and a ``favorite`` filter flag. Each shelf becomes a
personal list of its name: its comics are entries added by hand, and a
series, folder or other collection on it becomes a collection item that
stays current. Restoring is additive: a list of that name is reused.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from codex.user_data.store import SidecarStore


class RestoreReport(Protocol):
    """The part of the restore report this module writes to."""

    def note_written(self, table: str) -> None:
        """Count one restored row."""
        ...

    def note_skipped(self, table: str, reason: str) -> None:
        """Record one row that could not be restored."""
        ...


# List that favorites from a backup written before shelves existed are
# filed on, matching what the shelves migration named their shelf.
LEGACY_FAVORITES_SHELF_NAME: Final = "Favorites"
# A shelf whose name cleans to nothing, as the shelves migration names it.
_FALLBACK_LIST_NAME: Final = "Reading List"


def shelf_list_name(name: str) -> str:
    """
    Name a shelf's list as the shelves migration does: cleaned, never empty.

    A list name is cleaned on save and a shelf name never was. Unlike the
    migration, two shelves that clean to one name share the list: a restore
    reuses a list of that name, so running it again adds nothing.
    """
    from codex.models.readinglist import ReadingList

    clean = ReadingList._meta.get_field("name").get_prep_value
    return (clean(name) or "").strip() or _FALLBACK_LIST_NAME


def has_table(store: SidecarStore, table: str) -> bool:
    """Whether the sidecar carries ``table`` (older backups differ)."""
    row = (
        store.connection()
        .execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
        .fetchone()
    )
    return row is not None


def _list_of(user, name: str):
    """Return the user's personal list of this name, made if new."""
    from codex.models.readinglist import ReadingList

    reading_list, _ = ReadingList.objects.get_or_create(user=user, name=name)
    return reading_list


def restore_shelves(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore each shelf as a personal list, so empty shelves survive too."""
    from django.contrib.auth import get_user_model

    if not has_table(store, "shelves"):
        return
    user_model = get_user_model()
    for row in store.fetchall("shelves"):
        if dry_run:
            report.note_written("shelves")
            continue
        user = user_model.objects.filter(username=row["username"]).first()
        if user is None:
            report.note_skipped("shelves", f"missing user {row['username']!r}")
            continue
        _list_of(user, shelf_list_name(row["name"]))
        report.note_written("shelves")


class _ShelfRows:
    """Restore shelf item rows into lists; remember which lists changed."""

    def __init__(self, report: RestoreReport, resolve_pks: Callable) -> None:
        self.report = report
        self.resolve_pks = resolve_pks
        self.touched: set[int] = set()

    def _add_comics(self, reading_list, comic_pks) -> None:
        from django.db.models import Max

        from codex.librarian.scribe.readinglists.references import (
            comic_references,
            issue_name,
        )
        from codex.models import Comic
        from codex.models.readinglist import ReadingListEntry, ReadingListMatchTier

        held = set(
            ReadingListEntry.objects.filter(
                reading_list=reading_list,
                live_source__isnull=True,
                comic_id__in=comic_pks,
            ).values_list("comic_id", flat=True)
        )
        wanted = [pk for pk in comic_pks if pk not in held]
        if not wanted:
            return
        top = ReadingListEntry.objects.filter(reading_list=reading_list).aggregate(
            top=Max("position")
        )["top"]
        position = 0 if top is None else top + 1
        references = comic_references(wanted)
        comics = Comic.objects.filter(pk__in=wanted).select_related("series")
        ReadingListEntry.objects.bulk_create(
            ReadingListEntry(
                reading_list=reading_list,
                position=position + index,
                comic=comic,
                reference=references.get(comic.pk, {}),
                series_name=comic.series.name if comic.series_id else "",  # pyright: ignore[reportAttributeAccessIssue]
                issue=issue_name(comic.issue_number, comic.issue_suffix),
                year=comic.year,
                match_tier=ReadingListMatchTier.MANUAL,
                manual=True,
            )
            for index, comic in enumerate(comics)
        )

    @staticmethod
    def _add_missing(reading_list, path: str) -> bool:
        """
        Keep a shelved comic the library lacks as a missing issue.

        Named from its file, so the rematch after an import finds it; a
        restore run before the import finished used to drop it for good.
        Returns whether it is on the list.
        """
        from pathlib import Path

        from comicbox.readinglists import parse_issue
        from comicfn2dict import comicfn2dict
        from django.db.models import Max

        from codex.librarian.scribe.readinglists.references import issue_name
        from codex.models.readinglist import ReadingListEntry, ReadingListMatchTier

        parsed = comicfn2dict(Path(path).name)
        if not (series := str(parsed.get("series") or "")):
            return False
        number = parse_issue(parsed.get("issue"))
        issue = issue_name(number.number, number.suffix)
        year = int(raw) if (raw := str(parsed.get("year") or "")).isdigit() else None
        entries = ReadingListEntry.objects.filter(reading_list=reading_list)
        if entries.filter(
            comic__isnull=True, manual=True, series_name=series, issue=issue, year=year
        ).exists():
            return True
        reference: dict = {"series": {"name": series}}
        if issue:
            reference["issue"] = {"name": issue}
        if year:
            reference["date"] = {"year": year}
        top = entries.aggregate(top=Max("position"))["top"]
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            position=0 if top is None else top + 1,
            reference=reference,
            series_name=series,
            issue=issue,
            year=year,
            match_tier=ReadingListMatchTier.NONE,
            manual=True,
        )
        return True

    def _add_item(self, reading_list, collection: str, identity: str, pks) -> None:
        from codex.librarian.scribe.readinglists.live import (
            COLLECTION_KIND,
            ItemRefusedError,
            add_item,
        )
        from codex.models.readinglist import ReadingListSource

        for pk in pks:
            if ReadingListSource.objects.filter(
                reading_list=reading_list,
                kind=COLLECTION_KIND,
                collection=collection,
                target_id=pk,
            ).exists():
                return
            try:
                add_item(reading_list, collection, pk)
            except ItemRefusedError:
                continue
            else:
                return
        # Nothing of that identity here yet: keep it dangling, to bind later.
        ReadingListSource.objects.get_or_create(
            reading_list=reading_list,
            kind=COLLECTION_KIND,
            collection=collection,
            ref=identity[:1024],
            defaults={"document": {"identity": identity, "label": ""}},
        )

    def restore(self, row, table: str, list_name: str) -> None:
        from django.contrib.auth import get_user_model

        from codex.librarian.scribe.readinglists.live import ITEM_MODELS
        from codex.models.collection_models import BROWSE_COLLECTION_MODELS

        user = get_user_model().objects.filter(username=row["username"]).first()
        if user is None:
            self.report.note_skipped(table, f"missing user {row['username']!r}")
            return
        collection = row["collection"]
        target_model = BROWSE_COLLECTION_MODELS.get(collection)
        if target_model is None:
            self.report.note_skipped(table, f"unknown collection {collection!r}")
            return
        identity = row["identifier_json"]
        parts = json.loads(identity)[1:]
        pks = self.resolve_pks(collection, parts, target_model)
        reading_list = _list_of(user, shelf_list_name(list_name))
        if collection in ITEM_MODELS:
            self._add_item(reading_list, collection, identity, pks)
        elif pks:
            self._add_comics(reading_list, list(pks))
        elif not (parts and self._add_missing(reading_list, str(parts[0]))):
            self.report.note_skipped(
                table, f"unresolvable comic {parts!r} for user {row['username']!r}"
            )
            return
        self.touched.add(reading_list.pk)
        self.report.note_written(table)


def restore_shelf_items(
    store: SidecarStore,
    report: RestoreReport,
    resolve_pks: Callable,
    *,
    dry_run: bool,
) -> None:
    """Restore an older backup's shelf items and favorites into personal lists."""
    tables = [
        (table, name)
        for table, name in (
            ("shelf_items", ""),
            ("favorites", LEGACY_FAVORITES_SHELF_NAME),
        )
        if has_table(store, table)
    ]
    rows = _ShelfRows(report, resolve_pks)
    for table, name in tables:
        for row in store.fetchall(table):
            if dry_run:
                report.note_written(table)
                continue
            rows.restore(row, table, name or row["shelf_name"])
    if rows.touched:
        from codex.librarian.scribe.readinglists.live import sync_live

        sync_live(force=True, list_pks=rows.touched)


def resolve_filter_shelves(row, row_keys, browser) -> list[int]:
    """
    Resolve a filter row's shelf names to the owner's personal list pks.

    A backup written before shelves existed has a ``favorite`` flag
    instead; when set it becomes the owner's "Favorites" list, which the
    shelf restore has already made if they had any favorites.
    """
    from codex.models.readinglist import ReadingList

    names: list = []
    if "shelves" in row_keys:
        names = [shelf_list_name(name) for name in json.loads(row["shelves"] or "[]")]
    if "favorite" in row_keys and row["favorite"]:
        names.append(LEGACY_FAVORITES_SHELF_NAME)
    if not names or browser.user_id is None:
        return []
    return list(
        ReadingList.objects.filter(user_id=browser.user_id, name__in=names)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
