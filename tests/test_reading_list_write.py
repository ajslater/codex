"""
Writing a reading list into its comics' files, as a story arc.

The write is an additive per-comic patch that keeps other tag formats.
When the files come back through the importer, the arc's tags source
joins the list it was written from instead of making a second list.
"""

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client

from codex.choices.tagging import KEEP_WRITE_FORMAT
from codex.librarian.scribe.readinglists.service import copy_list
from codex.librarian.scribe.readinglists.sync import sync_tag_lists
from codex.librarian.scribe.readinglists.write import WRITTEN_ARC_KEY, arc_write
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_QUEUE: Final = "codex.views.admin.reading_lists.table.LIBRARIAN_QUEUE"
_NAME: Final = "Civil War (CBRO)"


class ReadingListWriteTests(ReadingListFixture):
    """A curated list written into files, then read back from them."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self.reading_list = ReadingList.objects.create(name=_NAME)  # pyright: ignore[reportUninitializedInstanceVariable]
        ReadingListSource.objects.create(
            reading_list=self.reading_list,
            kind=ReadingListSourceKind.UPLOAD,
            ref="cw.cbl",
            ordered=True,
        )
        c1, c2, c3, _ = self.comics
        # Place 2 is missing, place 4 hidden, and c3 is in it twice.
        for position, comic, ignored in (
            (0, c3, False),
            (1, None, False),
            (2, c1, False),
            (3, c2, True),
            (4, c3, False),
        ):
            ReadingListEntry.objects.create(
                reading_list=self.reading_list,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL,
                ignored=ignored,
            )
        admin = User.objects.create_user(
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def test_patches_number_by_first_place(self) -> None:
        """Numbers keep the list's gaps; hidden rows and repeats add nothing."""
        c1, _, c3, _ = self.comics
        arc = arc_write(self.reading_list)
        assert arc.name == _NAME
        assert arc.patches == {
            c3.pk: {"arcs": {_NAME: {"number": 1}}},
            c1.pk: {"arcs": {_NAME: {"number": 3}}},
        }

    def test_an_unordered_list_writes_no_numbers(self) -> None:
        """A list with no order tags its comics with the arc alone."""
        ReadingListSource.objects.update(ordered=False)
        arc = arc_write(self.reading_list)
        assert {pk: patch_["arcs"][_NAME] for pk, patch_ in arc.patches.items()} == {
            self.comics[2].pk: {},
            self.comics[0].pk: {},
        }

    def _write(self, reading_list: ReadingList) -> list:
        with patch(_QUEUE) as queue:
            response = self.client.post(
                f"/api/v4/admin/reading-lists/{reading_list.pk}/write"
            )
        assert response.status_code == _OK, response.content
        return [call.args[0] for call in queue.put.call_args_list]

    def test_the_write_is_additive_and_keeps_formats(self) -> None:
        """One additive tag write, keeping the comics' other formats."""
        (task,) = self._write(self.reading_list)
        assert isinstance(task, BulkTagWriteTask)
        assert task.mode == "additive"
        assert KEEP_WRITE_FORMAT in task.formats
        assert task.comic_pks == {self.comics[0].pk, self.comics[2].pk}
        self.reading_list.refresh_from_db()
        assert self.reading_list.extra[WRITTEN_ARC_KEY] == "civil war (cbro)"

    def test_a_list_with_its_arc_needs_no_mark(self) -> None:
        """A list already holding its arc as a tags source is not marked."""
        self.tag(self.comics[0], _NAME, 1)
        sync_tag_lists()
        tags_list = ReadingList.objects.exclude(pk=self.reading_list.pk).get()
        self._write(tags_list)
        tags_list.refresh_from_db()
        assert WRITTEN_ARC_KEY not in tags_list.extra

    def test_a_personal_list_is_not_written(self) -> None:
        """A personal list's name never goes into shared files."""
        owner = User.objects.create_user(username="owner", password=_PW)
        self.reading_list.user = owner
        self.reading_list.save()
        assert self._write(self.reading_list) == []

    def test_read_only_libraries_are_left_out(self) -> None:
        """No comic in a read-only library is queued."""
        self.library.read_only = True
        self.library.save()
        assert self._write(self.reading_list) == []

    def test_the_written_arc_joins_its_list(self) -> None:
        """Re-imported arc tags become this list's tags source, not a new list."""
        self._write(self.reading_list)
        # What the importer links once the files carry the arc.
        self.tag(self.comics[2], _NAME, 1)
        self.tag(self.comics[0], _NAME, 3)
        counts = sync_tag_lists()
        assert counts.created == 0
        assert ReadingList.objects.count() == 1
        self.reading_list.refresh_from_db()
        assert WRITTEN_ARC_KEY not in self.reading_list.extra
        kinds = set(
            ReadingListSource.objects.filter(
                reading_list=self.reading_list
            ).values_list("kind", flat=True)
        )
        assert kinds == {ReadingListSourceKind.UPLOAD, ReadingListSourceKind.TAGS}
        # The upload here holds no document, so the arc numbers order it.
        assert self.order(self.reading_list) == [self.comics[2].pk, self.comics[0].pk]

    def _read_back(self, reading_list: ReadingList) -> None:
        """Write the list, link its arc as the importer would, and sync."""
        self._write(reading_list)
        arc = arc_write(reading_list)
        for pk, patch_ in arc.patches.items():
            number = patch_["arcs"][arc.name].get("number")
            self.tag(Comic.objects.get(pk=pk), arc.name, number)
        sync_tag_lists()

    def test_a_hand_made_list_reads_back_once(self) -> None:
        """Written and re-imported, a list made by hand is not doubled."""
        c1, c2, c3, _ = self.comics
        hand = ReadingList.objects.create(name="Hand Made")
        for position, comic in enumerate((c1, None, c2, c3)):
            ReadingListEntry.objects.create(
                reading_list=hand,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL
                if comic
                else ReadingListMatchTier.NONE,
                manual=True,
            )
        self._read_back(hand)
        assert self.order(hand) == [c1.pk, None, c2.pk, c3.pk]

    def test_a_copied_list_reads_back_once(self) -> None:
        """A Copy to Global list, every entry by hand, reads back as it was."""
        c1, _, c3, _ = self.comics
        copy = copy_list(self.reading_list, user=None, name="Civil War Copy")
        assert self.order(copy) == [c3.pk, None, c1.pk, c3.pk]
        self._read_back(copy)
        assert self.order(copy) == [c3.pk, None, c1.pk, c3.pk]
        # The source rows hold the comics now; only the repeat and the
        # missing issue are still the list's own.
        manual = ReadingListEntry.objects.filter(reading_list=copy, manual=True)
        assert sorted(manual.values_list("position", flat=True)) == [1, 3]
