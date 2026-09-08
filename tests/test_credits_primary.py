"""
The primary credit flag, from the archive to the browser.

Comicbox 5 moved the flag off the person and onto each of their roles,
so a book's primary writer is not thereby also its primary inker. Codex
stores it on the person-and-role pairing, which is the same fact.
"""

from typing import override

from codex.models import Credit
from tests.importer.test_basic import BaseTestImporter, run_full_import


class CreditPrimaryImportTestCase(BaseTestImporter):
    """A full import of the fixture, then read the credit rows back."""

    @override
    def setUp(self) -> None:
        super().setUp()
        run_full_import(self.importer)

    @staticmethod
    def _flags() -> dict[tuple[str, str], bool]:
        # Every credit the fixture imports names both a person and a role.
        return {
            (credit.person.name, credit.role.name): credit.primary
            for credit in Credit.objects.select_related("person", "role")
            if credit.role
        }

    def test_the_flag_reaches_the_row(self) -> None:
        """The fixture's two primaries import as primary."""
        flags = self._flags()
        assert flags[("Joe Orlando", "Writer")] is True
        assert flags[("Wally Wood", "Penciller")] is True

    def test_primary_is_per_role_not_per_person(self) -> None:
        """
        The heart of the comicbox 5 change.

        Wally Wood is the fixture's primary penciller and also, without
        being primary, a writer. Under the old per-person flag the second
        role inherited the first one's primacy.
        """
        flags = self._flags()
        assert flags[("Wally Wood", "Penciller")] is True
        assert flags[("Wally Wood", "Writer")] is False
