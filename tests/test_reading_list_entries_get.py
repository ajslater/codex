"""
Edit Issues loads only what its rows show (C7).

The entries GET loaded every column of each entry, its comic, series and
volume, an entry's reference JSON included, which no row shows. It loads
only what ``entry_repr`` reads now. Reading anything else would cost a
query per row, so a query count guards it, and the rows are compared with
those of fully loaded entries.
"""

from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client

from codex.librarian.scribe.readinglists.live import add_item, reconcile_list
from codex.models import ReadingList, ReadingListEntry
from codex.models.readinglist import ReadingListMatchTier
from codex.views.readinglists.entries import entry_repr
from tests.test_reading_lists import ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_GET: Final = 12


class EntriesGetTests(ReadingListFixture):
    """A hand entry, a missing issue, a hidden one and a held volume."""

    @override
    def setUp(self) -> None:
        super().setUp()
        user = User.objects.create_user(username="u", password=_PW)
        self.client = Client()
        self.client.force_login(user)
        self.mine = ReadingList.objects.create(name="Mine", user=user)  # pyright: ignore[reportUninitializedInstanceVariable]
        c1, c2, _, _ = self.comics
        for position, (comic, ignored) in enumerate(
            ((c1, False), (None, False), (c2, True))
        ):
            ReadingListEntry.objects.create(
                reading_list=self.mine,
                position=position,
                comic=comic,
                ignored=ignored,
                series_name="Front Line" if comic is None else "",
                issue="1",
                reference={"series": {"name": "Front Line"}, "issue": {"name": "1"}},
                match_tier=ReadingListMatchTier.MANUAL,
                manual=True,
            )
        add_item(self.mine, "volumes", c1.volume_id)
        reconcile_list(self.mine)

    def test_the_rows_are_those_of_full_entries(self) -> None:
        with self.assertNumQueries(_GET):
            response = self.client.get(f"/api/v4/reading-lists/{self.mine.pk}/entries")
        assert response.status_code == _OK, response.content
        full = [
            entry_repr(entry)
            for entry in ReadingListEntry.objects.filter(reading_list=self.mine)
            .select_related("comic", "comic__series", "comic__volume")
            .order_by("position", "pk")
        ]
        assert response.json()["data"]["entries"] == full

    def test_a_filter_parameter_changes_nothing(self) -> None:
        """Every entry comes back, hidden ones too, whatever ``filter`` says."""
        url = f"/api/v4/reading-lists/{self.mine.pk}/entries"
        plain = self.client.get(url).json()["data"]
        assert [entry["ignored"] for entry in plain["entries"]].count(True) == 1
        for value in ("review", "missing", "hidden", "all", "bogus"):
            with self.subTest(filter=value):
                body = self.client.get(url, {"filter": value}).json()["data"]
                assert body == plain
