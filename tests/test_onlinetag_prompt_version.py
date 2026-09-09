"""
Prompts persisted under an older fingerprint scheme are dropped.

A deferred prompt is replayed by handing its fingerprint back to
comicbox, which matches it against the one the new lookup produces.
Comicbox 5 changed what goes into that fingerprint, so a prompt stored
by comicbox 4 can never match again: it would sit in the admin's review
queue forever, and answering it would silently do nothing.

This is a prune rather than a migration because the tagging cache lives
under the config directory, so a test run's migrations would reach a
developer's live prompts.
"""

from typing import override

from django.test import SimpleTestCase

from codex.librarian.onlinetag.session_cache import (
    PROMPT_VERSION,
    clear_all,
    get_pending_prompts,
    prune_stale_prompts,
    set_pending_prompts,
)

_CURRENT = {"fingerprint": "new", "prompt_version": PROMPT_VERSION, "pk": 1}
_OLD_SCHEME = {"fingerprint": "old", "pk": 2}


class PruneStalePromptsTestCase(SimpleTestCase):
    """The prune keeps what can still be answered."""

    @override
    def setUp(self) -> None:
        """Start from an empty cache."""
        super().setUp()
        clear_all()
        self.addCleanup(clear_all)

    def test_drops_only_the_unmatchable_ones(self) -> None:
        """A prompt from the old scheme goes; a current one stays."""
        set_pending_prompts({"new": _CURRENT, "old": _OLD_SCHEME})

        assert prune_stale_prompts() == 1
        assert set(get_pending_prompts()) == {"new"}

    def test_an_unstamped_prompt_is_from_before_the_stamp(self) -> None:
        """Every stored prompt predating the stamp predates the scheme."""
        set_pending_prompts({"old": _OLD_SCHEME})

        assert prune_stale_prompts() == 1
        assert not get_pending_prompts()

    def test_leaves_a_current_queue_alone(self) -> None:
        """Nothing to do is no writes and no loss."""
        set_pending_prompts({"new": _CURRENT})

        assert prune_stale_prompts() == 0
        assert get_pending_prompts() == {"new": _CURRENT}

    def test_is_idempotent(self) -> None:
        """It runs at every daemon start and every night."""
        set_pending_prompts({"new": _CURRENT, "old": _OLD_SCHEME})

        prune_stale_prompts()
        assert prune_stale_prompts() == 0
        assert set(get_pending_prompts()) == {"new"}

    def test_an_empty_queue_is_not_an_error(self) -> None:
        """The common case on a fresh install."""
        assert prune_stale_prompts() == 0
