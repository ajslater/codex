"""
``serialize_candidate`` carries what the match dialog needs to choose.

Two candidates can read identically — same series, issue and year — and
differ only in what the matcher blended their scores from. The reporter
of #854 hit exactly that: 92% and 84% with nothing on screen to tell
them apart.

The prompt endpoint tests seed prompts straight into the cache, so they
only prove camelCase passthrough of whatever dict is stored. These run
the serializer against real comicbox objects.
"""

from typing import Final

from comicbox.formats.base.online.profile import Candidate, CandidateSummary
from django.test import SimpleTestCase

from codex.librarian.onlinetag.session_cache import PROMPT_VERSION
from codex.librarian.onlinetag.session_state import serialize_candidate

_PROMPT_VERSION_AT_WRITING: Final = 2
_COVER_URL: Final = "https://static.metron.cloud/media/issue/x.jpg"
_METADATA_SCORE: Final = 1.0
_COVER_SCORE: Final = 0.6
_VOLUME: Final = 2


def _summary(
    *, cover_url: str = _COVER_URL, volume: int | None = None
) -> CandidateSummary:
    return CandidateSummary(
        series="Fight Club 3",
        issue="1",
        year=2019,
        publisher="Dark Horse",
        page_count=32,
        cover_url=cover_url,
        variant_label=None,
        volume=volume,
    )


def _candidate(
    summary: CandidateSummary,
    *,
    metadata_score: float = 0.0,
    cover_score: float | None = None,
    cover_hash_attempted: bool = False,
) -> Candidate:
    return Candidate(
        source="metron",
        issue_id=7,
        summary=summary,
        score=0.92,
        url="https://metron.cloud/issue/7",
        metadata_score=metadata_score,
        cover_score=cover_score,
        cover_hash_attempted=cover_hash_attempted,
    )


class SerializeCandidateTests(SimpleTestCase):
    """The display fields survive the trip to the dialog."""

    def test_score_components_are_carried(self) -> None:
        """The whole point: say what separated two identical-looking rows."""
        candidate = _candidate(
            _summary(),
            metadata_score=_METADATA_SCORE,
            cover_score=_COVER_SCORE,
            cover_hash_attempted=True,
        )

        data = serialize_candidate(candidate)

        assert data["metadata_score"] == _METADATA_SCORE
        assert data["cover_score"] == _COVER_SCORE
        assert data["cover_hash_attempted"] is True

    def test_an_uncompared_cover_is_distinguishable(self) -> None:
        """
        A missing cover score has two meanings.

        No usable image, or outside the top few the matcher pays to
        hash. The attempted flag is what tells them apart.
        """
        candidate = _candidate(_summary(), metadata_score=_METADATA_SCORE)

        data = serialize_candidate(candidate)

        assert data["cover_score"] is None
        assert data["cover_hash_attempted"] is False

    def test_the_volume_ordinal_is_carried(self) -> None:
        """Metron's issue rows carry one; Comic Vine's search rows do not."""
        with_volume = serialize_candidate(_candidate(_summary(volume=_VOLUME)))
        assert with_volume["summary"]["volume"] == _VOLUME
        assert serialize_candidate(_candidate(_summary()))["summary"]["volume"] is None

    def test_the_cover_url_is_passed_through_unchanged(self) -> None:
        """The browser loads it directly, so nothing may rewrite it."""
        url = "https://comicvine.gamespot.com/a/uploads/scale_avatar/1/2/3.jpg"
        data = serialize_candidate(_candidate(_summary(cover_url=url)))

        assert data["summary"]["cover_url"] == url

    def test_missing_attributes_do_not_raise(self) -> None:
        """An older comicbox must degrade to blank fields, not an exception."""

        class _Bare:
            source = "comicvine"
            issue_id = 1
            score = 0.5
            summary = object()

        data = serialize_candidate(_Bare())

        assert data["summary"]["series"] == ""
        assert data["metadata_score"] is None
        assert data["cover_score"] is None
        assert data["cover_hash_attempted"] is False
        assert data["volume_id"] is None

    def test_display_fields_do_not_bump_the_prompt_version(self) -> None:
        """
        Bumping it discards every pending prompt a user has queued.

        It gates the fingerprint scheme, not the payload shape.
        """
        assert PROMPT_VERSION == _PROMPT_VERSION_AT_WRITING
