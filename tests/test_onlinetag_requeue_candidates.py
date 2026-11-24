"""
A re-queued series prompt does not offer the old representative's issues.

A pick that names one issue cannot speak for the rest of the series, so
those comics go back in the queue under the same question. The candidates
were the representative's issues: choosing one again pinned its issue id,
and wrote that issue's tags onto a different comic.
"""

from unittest.mock import MagicMock

from django.core.cache import caches
from django.test import TestCase
from loguru import logger

from codex.librarian.onlinetag.prompt_apply import PromptApplier
from codex.librarian.onlinetag.session_cache import get_pending_prompts

_FINGERPRINT = "series-fingerprint"


class RequeueCandidatesTests(TestCase):
    """The followers' prompt keeps the question, not the representative's issues."""

    def test_the_requeued_prompt_drops_the_old_candidates(self) -> None:
        caches["tagging"].clear()
        prompt = {
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
        applier = PromptApplier(logger, MagicMock(), lambda: None)
        applier._requeue_untransferable(prompt, prompt["comics"][1:])  # noqa: SLF001
        requeued = get_pending_prompts()[_FINGERPRINT]
        assert [comic["pk"] for comic in requeued["comics"]] == [2, 3]
        assert requeued["pk"] == 2  # noqa: PLR2004
        assert requeued["candidates"] == []
