"""
Every librarian status names its finished work in good English.

A status without its own ``_verbed`` makes its past tense by adding "d" to
its verb, which is right only for a verb ending in "e": the reading-list
import logged "Import" with a bare "d" on the end. Every status class is
checked, so a new one cannot repeat it.
"""

import importlib
import pkgutil

from django.test import SimpleTestCase

import codex.librarian
from codex.librarian.scribe.readinglists.status import ReadingListImportStatus
from codex.librarian.status import Status


def _statuses() -> list[type[Status]]:
    """Return every status class with a verb, from every librarian module."""
    for module in pkgutil.walk_packages(
        codex.librarian.__path__, f"{codex.librarian.__name__}."
    ):
        importlib.import_module(module.name)
    found: list[type[Status]] = []
    pending: list[type[Status]] = [Status]
    while pending:
        for sub in pending.pop().__subclasses__():
            if sub not in found:
                found.append(sub)
                pending.append(sub)
    return [cls for cls in found if getattr(cls, "VERB", "")]


class StatusVerbedTests(SimpleTestCase):
    """The past tense every status shows when its work is done."""

    def test_a_derived_past_tense_is_spelled_right(self) -> None:
        statuses = _statuses()
        assert statuses
        for cls in statuses:
            with self.subTest(status=cls.__name__):
                verbed = cls.verbed()
                assert verbed != cls.VERB + "d" or cls.VERB.endswith("e"), verbed

    def test_the_reading_list_import(self) -> None:
        assert ReadingListImportStatus.verbed() == "Imported"
