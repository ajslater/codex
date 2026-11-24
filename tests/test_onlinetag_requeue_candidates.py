"""
A re-queued series prompt answers by volume, never by the old issue.

A pick that names one issue cannot speak for the rest of the series, so
those comics go back in the queue under the same question. Its candidates
are the first comic's issues: choosing one pinned that issue's id on the
next comic and wrote another issue's tags onto it. Dropping the candidates
fixed that but left only Skip, and lost the path a volume pick had to every
comic of the series. The candidates stay; on a re-queued prompt a choice
transfers its volume alone, to every comic, the first included.
"""

from typing import Any, override
from unittest.mock import MagicMock, patch

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.prompt_apply import PromptApplier
from codex.librarian.onlinetag.session_cache import get_pending_prompts
from tests.onlinetag_session_fakes import double

_FINGERPRINT = "series-fingerprint"
_VOLUME = 777


def _prompt() -> dict[str, Any]:
    return {
        "fingerprint": _FINGERPRINT,
        "source": "metron",
        "pk": 1,
        "path": "/comics/s1.cbz",
        "comics": [
            {"pk": 1, "path": "/comics/s1.cbz"},
            {"pk": 2, "path": "/comics/s2.cbz"},
            {"pk": 3, "path": "/comics/s3.cbz"},
        ],
        "candidates": [
            {"source": "metron", "issue_id": 111, "summary": {"issue": "1"}},
            {"source": "metron", "issue_id": 222, "summary": {"issue": "1"}},
        ],
    }


class RequeueCandidatesTests(TestCase):
    """The followers' prompt keeps the question and answers by volume."""

    @override
    def setUp(self) -> None:
        caches["tagging"].clear()
        self.applier = PromptApplier(double(logger), MagicMock(), MagicMock)  # pyright: ignore[reportUninitializedInstanceVariable]

    def _requeued(self) -> dict[str, Any]:
        prompt = _prompt()
        self.applier._requeue_untransferable(prompt, prompt["comics"][1:])  # noqa: SLF001
        return get_pending_prompts()[_FINGERPRINT]

    def _answer(self, prompt: dict[str, Any], volume: int | None):
        """Answer a prompt with its first candidate; return what was called."""
        applier = self.applier
        with (
            patch.object(applier, "_refresh_comic_path", side_effect=lambda _, p: p),
            patch.object(applier, "_apply_replayed_search") as replayed,
            patch.object(applier, "_apply_explicit_id") as explicit,
        ):
            applier.apply(prompt, "choose", 0, volume)
        return replayed, explicit

    def test_the_requeued_prompt_keeps_its_question(self) -> None:
        requeued = self._requeued()
        assert [comic["pk"] for comic in requeued["comics"]] == [2, 3]
        assert requeued["pk"] == 2  # noqa: PLR2004
        assert [c["issue_id"] for c in requeued["candidates"]] == [111, 222]

    def test_a_volume_choice_replays_every_comic(self) -> None:
        """No comic is pinned to the first comic's issue, the new first one too."""
        replayed, explicit = self._answer(self._requeued(), _VOLUME)
        explicit.assert_not_called()
        assert [call.args[1] for call in replayed.call_args_list] == [2, 3]

    def test_a_choice_with_no_volume_asks_again(self) -> None:
        """Nothing transfers, so nothing is written and the comics wait."""
        requeued = self._requeued()
        caches["tagging"].clear()
        replayed, explicit = self._answer(requeued, None)
        explicit.assert_not_called()
        replayed.assert_not_called()
        again = get_pending_prompts()[_FINGERPRINT]
        assert [comic["pk"] for comic in again["comics"]] == [2, 3]
