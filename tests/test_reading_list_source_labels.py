"""The names people read for a reading list's sources."""

from codex.choices.readinglists import READING_LIST_CHOICES, ReadingListSourceKind


def test_a_tags_source_is_named_for_story_arcs() -> None:
    """A ``tags`` source only ever comes from story arc tags, so says so."""
    assert ReadingListSourceKind.TAGS.label == "Story Arc Tags"
    assert READING_LIST_CHOICES["source_kinds"]["tags"] == "Story Arc Tags"
