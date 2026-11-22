"""
Restore shelves from the user-data sidecar.

Split out of :mod:`codex.user_data.restore`. Covers the current
``shelves`` / ``shelf_items`` tables and the ``favorites`` table and
``favorite`` filter flag of a backup written before shelves existed.
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


# Shelf that favorites from a backup written before shelves existed are
# filed on, matching what the shelves migration names it.
LEGACY_FAVORITES_SHELF_NAME: Final = "Favorites"


def has_table(store: SidecarStore, table: str) -> bool:
    """Whether the sidecar carries ``table`` (older backups differ)."""
    row = (
        store.connection()
        .execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
        .fetchone()
    )
    return row is not None


def restore_shelves(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Restore Shelf rows, so empty shelves survive a round trip."""
    from django.contrib.auth import get_user_model

    from codex.models.shelf import Shelf

    user_model = get_user_model()
    for row in store.fetchall("shelves"):
        if dry_run:
            report.note_written("shelves")
            continue
        user = user_model.objects.filter(username=row["username"]).first()
        if user is None:
            report.note_skipped("shelves", f"missing user {row['username']!r}")
            continue
        Shelf.objects.get_or_create(user=user, name=row["name"])
        report.note_written("shelves")


def _restore_shelf_item_rows(
    rows,
    table: str,
    report: RestoreReport,
    resolve_pks: Callable,
    *,
    dry_run: bool,
    shelf_name: str = "",
) -> None:
    """
    Restore shelf item rows; resolve identifier_json → main-DB PK.

    ``shelf_name`` overrides the row's own shelf for the legacy
    ``favorites`` table, whose rows name no shelf.
    """
    from django.contrib.auth import get_user_model

    from codex.models.collection_models import BROWSE_COLLECTION_MODELS
    from codex.models.shelf import Shelf, ShelfItem

    user_model = get_user_model()
    for row in rows:
        if dry_run:
            report.note_written(table)
            continue
        user = user_model.objects.filter(username=row["username"]).first()
        if user is None:
            report.note_skipped(table, f"missing user {row['username']!r}")
            continue
        collection = row["collection"]
        target_model = BROWSE_COLLECTION_MODELS.get(collection)
        if target_model is None:
            report.note_skipped(table, f"unknown shelf collection {collection!r}")
            continue
        decoded = json.loads(row["identifier_json"])
        # decoded == [collection, ...parts]
        parts = decoded[1:]
        target_pks = resolve_pks(collection, parts, target_model)
        if not target_pks:
            username = row["username"]
            report.note_skipped(
                table,
                f"unresolvable {collection!r} target {parts!r} for user {username!r}",
            )
            continue
        shelf, _ = Shelf.objects.get_or_create(
            user=user, name=shelf_name or row["shelf_name"]
        )
        for target_pk in target_pks:
            ShelfItem.objects.get_or_create(
                shelf=shelf, collection=collection, target_id=target_pk
            )
        report.note_written(table)


def restore_shelf_items(
    store: SidecarStore,
    report: RestoreReport,
    resolve_pks: Callable,
    *,
    dry_run: bool,
) -> None:
    """Restore shelf items, and the favorites of a pre-shelves backup."""
    _restore_shelf_item_rows(
        store.fetchall("shelf_items"),
        "shelf_items",
        report,
        resolve_pks,
        dry_run=dry_run,
    )
    if has_table(store, "favorites"):
        _restore_shelf_item_rows(
            store.fetchall("favorites"),
            "favorites",
            report,
            resolve_pks,
            dry_run=dry_run,
            shelf_name=LEGACY_FAVORITES_SHELF_NAME,
        )


def resolve_filter_shelves(row, row_keys, browser) -> list[int]:
    """
    Resolve a filter row's shelf names back to the owner's shelf pks.

    A backup written before shelves existed has a ``favorite`` flag
    instead; when set it becomes the owner's "Favorites" shelf, which the
    shelf restore has already created if they had any favorites.
    """
    from codex.models.shelf import Shelf

    names: list = []
    if "shelves" in row_keys:
        names = json.loads(row["shelves"] or "[]")
    if "favorite" in row_keys and row["favorite"]:
        names.append(LEGACY_FAVORITES_SHELF_NAME)
    if not names:
        return []
    return list(
        Shelf.objects.filter(user_id=browser.user_id, name__in=names)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
