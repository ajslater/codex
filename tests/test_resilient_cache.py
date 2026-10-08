"""
A cache entry pickled against code that is gone reads as a miss, not a 500.

Codex 2.5.3 pickled comicbox's ``numpy.float64`` cover scores into
pending online-tag prompts. 2.5.4 ships without numpy, so every read of
the prompts (the daemon's startup prune, the review list, the session
snapshot) raised ``ModuleNotFoundError``. These tests store a value whose
class lives in a throwaway module, then take the module, or just the
class, away.
"""

import sys
from types import ModuleType
from typing import Final, override

from django.test import SimpleTestCase
from loguru import logger

from codex.cache import tagging_cache
from codex.librarian.onlinetag.session_cache import (
    PROMPT_VERSION,
    clear_all,
    get_pending_prompts,
    prune_stale_prompts,
    set_pending_prompts,
)

_MODULE_NAME: Final = "codex_tests_vanishing_dependency"
_CLASS_NAME: Final = "LibraryFloat"
_KEY: Final = "tests:stale_pickle"
_MISS: Final = "miss"


class StalePickleTestCase(SimpleTestCase):
    """Entries naming a missing module or class are discarded."""

    @override
    def setUp(self) -> None:
        """Install a module defining a float subclass, like numpy.float64."""
        super().setUp()
        self.module = ModuleType(_MODULE_NAME)  # pyright: ignore[reportUninitializedInstanceVariable]
        library_float = type(_CLASS_NAME, (float,), {"__module__": _MODULE_NAME})
        setattr(self.module, _CLASS_NAME, library_float)
        sys.modules[_MODULE_NAME] = self.module
        self.addCleanup(sys.modules.pop, _MODULE_NAME, None)
        clear_all()
        self.addCleanup(clear_all)
        self.addCleanup(tagging_cache.delete, _KEY)

    def _library_float(self, value: float) -> float:
        return getattr(self.module, _CLASS_NAME)(value)

    def _uninstall_module(self) -> None:
        del sys.modules[_MODULE_NAME]

    def test_a_missing_module_is_a_miss(self) -> None:
        """The dependency was dropped: ``ModuleNotFoundError`` on load."""
        tagging_cache.set(_KEY, {"cover_score": self._library_float(0.6)})
        self._uninstall_module()

        assert tagging_cache.get(_KEY, _MISS) == _MISS
        assert not tagging_cache.has_key(_KEY)

    def test_a_missing_class_is_a_miss(self) -> None:
        """The class was removed or renamed: ``AttributeError`` on load."""
        tagging_cache.set(_KEY, {"cover_score": self._library_float(0.6)})
        delattr(self.module, _CLASS_NAME)

        assert tagging_cache.get(_KEY, _MISS) == _MISS
        assert not tagging_cache.has_key(_KEY)

    def test_the_discard_is_logged_with_its_cause(self) -> None:
        """
        The file is gone afterwards, so the log is the only evidence.

        It must name the key and carry the traceback, in case this ever
        catches an error it should not.
        """
        tagging_cache.set(_KEY, {"cover_score": self._library_float(0.6)})
        self._uninstall_module()
        records: list[str] = []
        sink_id = logger.add(records.append, level="WARNING", format="{message}")
        try:
            tagging_cache.get(_KEY)
        finally:
            logger.remove(sink_id)

        assert len(records) == 1
        assert _KEY in records[0]
        assert "ModuleNotFoundError" in records[0]
        assert "Traceback" in records[0]

    def test_touch_discards_it_too(self) -> None:
        """``touch`` unpickles the value to rewrite it with a new expiry."""
        tagging_cache.set(_KEY, {"cover_score": self._library_float(0.6)})
        self._uninstall_module()

        assert tagging_cache.touch(_KEY) is False
        assert not tagging_cache.has_key(_KEY)

    def test_stale_prompts_do_not_break_the_startup_prune(self) -> None:
        """The reported failure: the daemon reads every prompt at startup."""
        candidate = {"score": self._library_float(0.9)}
        prompt = {"prompt_version": PROMPT_VERSION, "candidates": [candidate]}
        set_pending_prompts({"fp": prompt})
        self._uninstall_module()

        assert prune_stale_prompts() == 0
        assert get_pending_prompts() == {}
