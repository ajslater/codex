"""
Credit key tuples carry every part of their key.

A credit is keyed on the person, the role and whether the person is that
role's primary holder. A key built short is padded with nulls on its way
into the database, which the primary flag does not accept, so a shape
that produces a short key takes the whole import down with an
IntegrityError rather than losing one row.
"""

import shutil
from multiprocessing import Event
from pathlib import Path
from threading import Lock
from typing import override

from django.test import TestCase
from loguru import logger

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.importer.const import (
    LINK_M2MS,
    QUERY_MODELS,
    get_key_index,
)
from codex.librarian.scribe.importer.importer import ComicImporter
from codex.librarian.scribe.importer.tasks import ImportTask
from codex.models import Library
from codex.models.named import Credit

TMP_DIR = Path("/tmp/codex.tests.credits")  # noqa: S108
_PATH = TMP_DIR / "c.cbz"


class CreditKeyShapeTestCase(TestCase):
    """Every credit shape a file can state produces a whole key."""

    @override
    def setUp(self) -> None:
        """Build an importer to run the m2m aggregation through."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        task = ImportTask(library_id=library.pk, files_modified=frozenset({str(_PATH)}))
        self.importer = ComicImporter(  # pyright: ignore[reportUninitializedInstanceVariable]
            task, logger, LIBRARIAN_QUEUE, Lock(), Event()
        )

    @override
    def tearDown(self) -> None:
        """Remove the temp dir."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        super().tearDown()

    def _credit_keys(self, credits_md: dict) -> set[tuple]:
        self.importer.metadata[QUERY_MODELS] = {}
        self.importer.metadata[LINK_M2MS] = {}
        self.importer.get_m2m_metadata({"credits": credits_md}, _PATH)
        return self.importer.metadata[LINK_M2MS][str(_PATH)]["credits"]

    def test_a_role_names_its_primary_holder(self) -> None:
        """The ordinary shape: a person, a role, and the flag."""
        keys = self._credit_keys(
            {
                "Joe Orlando": {"roles": {"Writer": {"primary": True}}},
                "Wally Wood": {"roles": {"Inker": {}}},
            }
        )

        assert keys == {("Joe Orlando", "Writer", True), ("Wally Wood", "Inker", False)}

    def test_a_person_credited_with_no_role_still_keys_a_row(self) -> None:
        """
        A file may credit someone without saying what they did.

        There is no role for them to be the primary holder of, so the
        flag is false rather than absent — absent is what the database
        refuses.
        """
        keys = self._credit_keys({"Nameless Contributor": {}})

        assert keys == {("Nameless Contributor", None, False)}

    def test_every_shape_fills_the_whole_key(self) -> None:
        """
        The invariant behind both cases above.

        Whatever a file states, a credit key has as many parts as the
        key has columns; a short one is padded with nulls the primary
        flag rejects.
        """
        keys = self._credit_keys(
            {
                "With Roles": {"roles": {"Writer": {"primary": True}, "Inker": {}}},
                "Without Roles": {},
                "Empty Roles": {"roles": {}},
            }
        )

        width = get_key_index(Credit)
        assert keys
        for key in keys:
            assert len(key) == width, key
            assert key[-1] in (True, False), key
