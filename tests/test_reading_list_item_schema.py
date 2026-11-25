"""
A collection item: a whole series, folder or list held in a reading list.

It is a source of kind ``collection`` bound to its target by
``(collection, target_id)``. Its comics are live entries that go with it.
"""

from typing import Final

import pytest
from django.db import IntegrityError, transaction

from codex.librarian.scribe.readinglists.service import remove_source
from codex.models import ReadingList, ReadingListEntry, ReadingListSource
from codex.models.readinglist import ReadingListMatchTier, ReadingListSourceKind
from tests.test_reading_lists import ReadingListFixture

_COLLECTION: Final = ReadingListSourceKind.COLLECTION
_IDENTITY: Final = '["Marlow", "Marlow", "Civil War"]'


def _count(reading_list: ReadingList) -> int:
    return ReadingListSource.objects.filter(reading_list=reading_list).count()


class ItemSchemaTests(ReadingListFixture):
    """What the database allows for collection items."""

    def _item(self, reading_list, target_id=None, ref=_IDENTITY, collection="series"):
        return ReadingListSource.objects.create(
            reading_list=reading_list,
            kind=_COLLECTION,
            collection=collection,
            target_id=target_id,
            ref=ref,
        )

    def test_one_item_per_row(self) -> None:
        """A series sits in a list once."""
        reading_list = ReadingList.objects.create(name="Mine")
        series_pk = self.comics[0].series_id
        self._item(reading_list, series_pk)
        with pytest.raises(IntegrityError), transaction.atomic():
            self._item(reading_list, series_pk, ref="another identity")

    def test_two_rows_may_share_an_identity(self) -> None:
        """Two folders of one path in two libraries are two items."""
        reading_list = ReadingList.objects.create(name="Mine")
        self._item(reading_list, 1, ref="/comics", collection="folders")
        self._item(reading_list, 2, ref="/comics", collection="folders")
        assert _count(reading_list) == 2  # noqa: PLR2004

    def test_items_of_other_collections_may_share_a_pk(self) -> None:
        """Series 1 and publisher 1 are different rows."""
        reading_list = ReadingList.objects.create(name="Mine")
        self._item(reading_list, 1, collection="series")
        self._item(reading_list, 1, collection="publishers")
        assert _count(reading_list) == 2  # noqa: PLR2004

    def test_an_item_and_a_document_may_share_a_ref(self) -> None:
        """References are unique per kind of source."""
        reading_list = ReadingList.objects.create(name="Mine")
        self._item(reading_list, None, ref="civil-war.cbl")
        ReadingListSource.objects.create(
            reading_list=reading_list,
            kind=ReadingListSourceKind.UPLOAD,
            ref="civil-war.cbl",
        )
        assert _count(reading_list) == 2  # noqa: PLR2004

    def test_live_entries_go_with_their_item(self) -> None:
        """Removing an item removes the comics it delivered, nothing else."""
        reading_list = ReadingList.objects.create(name="Mine")
        c1, c2, _, _ = self.comics
        item = self._item(reading_list, c1.series_id)
        ReadingListEntry.objects.create(
            reading_list=reading_list,
            comic=c1,
            live_source=item,
            match_tier=ReadingListMatchTier.COLLECTION,
        )
        kept = ReadingListEntry.objects.create(
            reading_list=reading_list, comic=c2, manual=True, position=1
        )
        item.delete()
        assert list(ReadingListEntry.objects.filter(reading_list=reading_list)) == [
            kept
        ]

    def test_removing_the_last_item_keeps_a_global_list(self) -> None:
        """A list never goes with a collection item."""
        reading_list = ReadingList.objects.create(name="Everything Marlow")
        item = self._item(reading_list, self.comics[0].series_id)
        assert remove_source(item)
        assert ReadingList.objects.filter(pk=reading_list.pk).exists()
