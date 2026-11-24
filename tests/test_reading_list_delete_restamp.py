"""
A comic that leaves the library re-stamps the reading lists that held it.

The browser's refresh probe reads a list's own ``updated_at``. The delete
and revival passes collect the collections a comic belongs to before they
change it, so the timestamp updater re-stamps each one, lists included.
"""

import threading
from datetime import timedelta

from django.utils import timezone
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.delete.collect import (
    init_comic_collection_map,
    populate_comic_collection_map,
)
from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.models import Comic, ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import ReadingListFixture


class DeleteRestampTests(ReadingListFixture):
    """A deleted comic's lists are re-stamped, the way its series is."""

    def test_a_deleted_comics_list_is_restamped(self) -> None:
        """The list that held the comic gets a new ``updated_at``."""
        c1, c2, _, _ = self.comics
        reading_list = ReadingList.objects.create(name="Event")
        for position, comic in enumerate((c1, c2)):
            ReadingListEntry.objects.create(
                reading_list=reading_list,
                position=position,
                comic=comic,
                match_tier=ReadingListMatchTier.MANUAL,
            )
        # Nothing else changed today, so only the delete can re-stamp it.
        before = timezone.now() - timedelta(days=1)
        ReadingList.objects.filter(pk=reading_list.pk).update(updated_at=before)
        Comic.objects.update(updated_at=before)

        collection_map = init_comic_collection_map()
        populate_comic_collection_map(Comic.objects.filter(pk=c1.pk), collection_map)
        Comic.objects.filter(pk=c1.pk).delete()
        TimestampUpdater(
            logger, LIBRARIAN_QUEUE, threading.Lock()
        ).update_library_collections(self.library, timezone.now(), collection_map)

        reading_list.refresh_from_db()
        assert reading_list.updated_at > before
