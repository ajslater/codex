"""A reading list card's sources line: short labels, as cover captions join."""

from codex.models import ReadingList
from codex.models.readinglist import ReadingListSource, ReadingListSourceKind
from codex.views.browser.reading_list_sources import attach_list_sources
from tests.test_reading_lists import ReadingListFixture


class CardSourcesTests(ReadingListFixture):
    """Several sources join with a comma, as other cover captions do."""

    def test_sources_join_with_a_comma(self) -> None:
        """A list from tags with an upload attributed to CBRO."""
        reading_list = ReadingList.objects.create(name="Civil War")
        ReadingListSource.objects.create(
            reading_list=reading_list, kind=ReadingListSourceKind.TAGS, rank=0
        )
        ReadingListSource.objects.create(
            reading_list=reading_list,
            kind=ReadingListSourceKind.UPLOAD,
            ref="x.cbl",
            attribution_source="cbro",
            rank=1,
        )
        lists = ReadingList.objects.filter(pk=reading_list.pk)
        attach_list_sources(lists)
        (row,) = lists
        # The comma may wrap; a source and its attribution stay together.
        assert row.list_sources == "Tags, Upload\u00a0·\u00a0CBRO"  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[missing-attribute]
