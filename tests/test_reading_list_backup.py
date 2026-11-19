"""
Reading lists survive a backup and restore.

The sidecar keeps every list a person made or imported: its header, its
sources with their documents, its entries with their comics by path and
every hand edit, and the series mappings. A list that only mirrors its
story-arc tags is left out: the sync rebuilds it from the tags.
"""

import sqlite3
from typing import Any, Final, override

from django.contrib.auth.models import User

from codex.librarian.scribe.readinglists.service import combine_lists, import_document
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.models import (
    ReadingList,
    ReadingListEntry,
    ReadingListSeriesMapping,
    ReadingListSource,
)
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from codex.user_data import store as store_module
from codex.user_data.dump import dump_user_data
from codex.user_data.dump_reading_lists import READING_LIST_TABLES
from codex.user_data.restore import restore
from codex.user_data.store import SidecarStore, reset_store_for_tests
from codex.views.readinglists.entries import add_comics
from tests.test_reading_list_combine import _document, _upload
from tests.test_reading_lists import TMP_DIR, ReadingListFixture

_PW: Final = "test-pw-hush-S106"


def _entries(reading_list: ReadingList) -> list[tuple[Any, ...]]:
    """Every entry as a person or the matcher left it, in order."""
    sources = {
        source.pk: (source.kind, source.ref)
        for source in ReadingListSource.objects.filter(reading_list=reading_list)
    }
    return [
        (
            entry.position,
            entry.comic_id,  # pyright: ignore[reportAttributeAccessIssue]
            entry.reference,
            entry.series_name,
            entry.issue,
            entry.year,
            entry.match_tier,
            entry.needs_review,
            entry.ignored,
            entry.manual,
            entry.entry_type,
            sorted(sources[pk] for pk in entry.source_ids),
        )
        for entry in ReadingListEntry.objects.filter(
            reading_list=reading_list
        ).order_by("position", "pk")
    ]


def _sources(reading_list: ReadingList) -> list[tuple[Any, ...]]:
    return list(
        ReadingListSource.objects.filter(reading_list=reading_list)
        .order_by("rank", "pk")
        .values_list(
            "kind",
            "ref",
            "revision",
            "attribution_source",
            "rank",
            "ordered",
            "document",
        )
    )


def _state() -> dict:
    """Everything the backup must bring back, keyed by list uuid."""
    lists = {}
    for reading_list in ReadingList.objects.select_related("user"):
        lists[str(reading_list.uuid)] = {
            "name": reading_list.name,
            "user": reading_list.user.username if reading_list.user else None,
            "order_locked": reading_list.order_locked,
            "edited_fields": reading_list.edited_fields,
            "description": reading_list.description,
            "list_type": reading_list.list_type,
            "sources": _sources(reading_list),
            "entries": _entries(reading_list),
        }
    mappings = sorted(
        ReadingListSeriesMapping.objects.values_list("series_key", "year", "series_id")
    )
    return {"lists": lists, "mappings": mappings}


class ReadingListBackupTests(ReadingListFixture):
    """Dump, wipe, restore, compare."""

    @override
    def setUp(self) -> None:
        super().setUp()
        config = TMP_DIR / "config"
        config.mkdir(parents=True, exist_ok=True)
        self.store = SidecarStore(config / "user_data.sqlite")  # pyright: ignore[reportUninitializedInstanceVariable]
        store_module._store = self.store  # noqa: SLF001
        self.user = User.objects.create_user(username="alice", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        self.store.close()
        reset_store_for_tests(None)
        super().tearDown()

    def _snapshot(self):
        dump_user_data()
        self.store.connection().execute("PRAGMA wal_checkpoint(FULL)")
        snapshot = TMP_DIR / "config" / "snapshot.sqlite"
        with sqlite3.connect(snapshot) as dst:
            self.store.connection().backup(dst)
        return snapshot

    def _seed(self) -> None:
        """Make a combined global list with hand edits, a personal list, a mapping."""
        c1, c2, c3, c4 = self.comics
        self.tag(c1, "Civil War", 1)
        self.tag(c2, "Civil War", 2)
        sync_tag_lists()
        tags_list = ReadingList.objects.get(name="Civil War")
        curated = import_document(_document(), _upload())
        combined = combine_lists(tags_list, [curated])
        entries = list(
            ReadingListEntry.objects.filter(reading_list=combined).order_by("position")
        )
        entries[1].comic = c4
        entries[1].match_tier = ReadingListMatchTier.MANUAL
        entries[1].save()
        entries[3].ignored = True
        entries[3].save()
        add_comics(combined, [c3.pk])
        mine = ReadingList.objects.create(name="Mine", user=self.user)
        add_comics(mine, [c2.pk, c1.pk])
        ReadingListEntry.objects.filter(reading_list=mine, comic=c1).update(
            match_tier=ReadingListMatchTier.MARKED_MISSING, comic=None
        )
        ReadingListSeriesMapping.objects.create(
            series_key="the amazing spider man", year=1963, series=c1.series
        )
        # Arcs that only mirror their tags are rebuilt, not backed up.
        self.tag(c3, "Other Arc", 1)
        sync_tag_lists()

    def test_round_trip(self) -> None:
        """Lists, sources, entries and mappings come back as they were."""
        self._seed()
        before = _state()
        snapshot = self._snapshot()
        ReadingList.objects.all().delete()
        ReadingListSeriesMapping.objects.all().delete()
        report = restore(sidecar_path=snapshot)
        assert report.written.get("reading_lists") == 2  # noqa: PLR2004
        after = _state()
        # The tags-only list is rebuilt by the sync, with a new uuid.
        other = next(
            uuid for uuid, row in before["lists"].items() if row["name"] == "Other Arc"
        )
        expected = dict(before["lists"])
        del expected[other]
        assert after["mappings"] == before["mappings"]
        assert after["lists"] == expected

    def test_restore_replaces_a_list_the_sync_rebuilt(self) -> None:
        """A rebuilt database's tags-only copy of an arc gives way to the backup."""
        self._seed()
        before = _state()
        snapshot = self._snapshot()
        ReadingList.objects.all().delete()
        sync_tag_lists()
        restore(sidecar_path=snapshot)
        holders = ReadingListSource.objects.filter(
            kind=ReadingListSourceKind.TAGS, ref="civil war"
        ).values_list("reading_list__uuid", flat=True)
        civil_war = next(
            uuid for uuid, row in before["lists"].items() if row["name"] == "Civil War"
        )
        assert [str(uuid) for uuid in holders] == [civil_war]

    def test_restore_is_idempotent(self) -> None:
        """A second restore changes nothing."""
        self._seed()
        snapshot = self._snapshot()
        restore(sidecar_path=snapshot)
        once = _state()
        restore(sidecar_path=snapshot)
        assert _state() == once

    def test_a_backup_from_before_lists_restores(self) -> None:
        """A sidecar without the reading list tables restores the rest."""
        self._seed()
        snapshot = self._snapshot()
        with sqlite3.connect(snapshot) as conn:
            for table in READING_LIST_TABLES:
                conn.execute(f"DROP TABLE {table}")
        count = ReadingList.objects.count()
        report = restore(sidecar_path=snapshot)
        assert "reading_lists" not in report.written
        assert ReadingList.objects.count() == count

    def test_dry_run_writes_nothing(self) -> None:
        """A dry run resolves the rows and saves none."""
        self._seed()
        snapshot = self._snapshot()
        ReadingList.objects.all().delete()
        restore(sidecar_path=snapshot, dry_run=True)
        assert not ReadingList.objects.exists()
