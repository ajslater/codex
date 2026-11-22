"""
OPDS v2 start page: one preview group per reading list of the user's own.

Ported from the shelves start-page tests when shelves folded into lists.
The groups are built per request from the user's own lists, so the things
to pin are that a list shows its comics, in order, that a series it holds
shows its issues, that an empty list adds nothing, and that nobody sees
another user's list.
"""

from codex.librarian.scribe.readinglists.live import add_item, reconcile_list
from codex.models import ReadingList
from codex.views.readinglists.entries import add_comics
from tests.test_opds_keep_reading import (
    _TEST_PASSWORD,
    KeepReadingSeedTestCase,
    _group,
    _pks,
)

_LIST_NAME = "Want to Read"


class OPDSReadingListsTestCase(KeepReadingSeedTestCase):
    """Per-user reading list preview groups on the v2 start feed."""

    def _login(self, user) -> None:
        assert self.client.login(username=user.username, password=_TEST_PASSWORD)

    def _list(self) -> ReadingList:
        return ReadingList.objects.create(user=self.user, name=_LIST_NAME)

    def test_a_list_is_a_start_page_group_holding_its_comics(self) -> None:
        """Its comics, in the list's order."""
        reading_list = self._list()
        add_comics(reading_list, [self.comics[4].pk, self.comics[1].pk])
        self._login(self.user)

        group = _group(self._feed(self.client), _LIST_NAME)

        assert group is not None
        assert _pks(group) == [self.comics[4].pk, self.comics[1].pk]

    def test_a_held_series_shows_its_issues(self) -> None:
        """A series held whole previews its comics."""
        reading_list = self._list()
        add_item(reading_list, "series", self.comics[0].series_id)
        reconcile_list(reading_list)
        self._login(self.user)

        group = _group(self._feed(self.client), _LIST_NAME)

        assert group is not None
        assert set(_pks(group)) <= {comic.pk for comic in self.comics}
        assert _pks(group)

    def test_the_list_link_states_every_browser_parameter(self) -> None:
        """OPDS settings persist, so an omitted parameter would be inherited."""
        reading_list = self._list()
        add_comics(reading_list, [self.comics[0].pk])
        self._login(self.user)

        group = _group(self._feed(self.client), _LIST_NAME)

        assert group is not None
        hrefs = [link["href"] for link in group.get("links", [])]
        assert hrefs, group
        for param in ("filters=", "orderBy=", "orderReverse=", "topCollection="):
            assert any(param in href for href in hrefs), (param, hrefs)
        assert any(f"%5B{reading_list.pk}%5D" in href for href in hrefs), hrefs

    def test_an_empty_list_adds_no_group(self) -> None:
        """Nothing to preview, no section."""
        self._list()
        self._login(self.user)

        assert _group(self._feed(self.client), _LIST_NAME) is None

    def test_other_users_and_anonymous_do_not_see_the_list(self) -> None:
        """A personal list is its owner's alone."""
        add_comics(self._list(), [self.comics[0].pk])

        assert _group(self._feed(self.client), _LIST_NAME) is None
        self._login(self.other)
        assert _group(self._feed(self.client), _LIST_NAME) is None
