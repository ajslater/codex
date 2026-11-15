"""
OPDS v2 start page: one preview group per shelf of the requesting user.

Shelves replaced the single static Favorites group. The groups are built
per request from the user's own shelves, so the things to pin are that a
shelf shows its comics, that an empty shelf adds nothing, and that nobody
sees another user's shelf.
"""

from codex.models import Shelf, ShelfItem
from tests.test_opds_keep_reading import (
    _TEST_PASSWORD,
    KeepReadingSeedTestCase,
    _group,
    _pks,
)

_SHELF_NAME = "Want to Read"


class OPDSShelvesTestCase(KeepReadingSeedTestCase):
    """Per-user shelf preview groups on the v2 start feed."""

    def _login(self, user) -> None:
        assert self.client.login(username=user.username, password=_TEST_PASSWORD)

    def test_a_shelf_is_a_start_page_group_holding_its_comics(self) -> None:
        shelf = Shelf.objects.create(user=self.user, name=_SHELF_NAME)
        for comic in (self.comics[1], self.comics[4]):
            ShelfItem.objects.create(
                shelf=shelf, collection="comics", target_id=comic.pk
            )
        self._login(self.user)

        group = _group(self._feed(self.client), _SHELF_NAME)

        assert group is not None
        assert sorted(_pks(group)) == sorted([self.comics[1].pk, self.comics[4].pk])

    def test_a_shelved_series_shows_its_issues(self) -> None:
        shelf = Shelf.objects.create(user=self.user, name=_SHELF_NAME)
        ShelfItem.objects.create(
            shelf=shelf, collection="series", target_id=self.comics[0].series_id
        )
        self._login(self.user)

        group = _group(self._feed(self.client), _SHELF_NAME)

        assert group is not None
        assert set(_pks(group)) <= {comic.pk for comic in self.comics}
        assert _pks(group)

    def test_the_shelf_link_states_every_browser_parameter(self) -> None:
        """OPDS settings persist, so an omitted parameter would be inherited."""
        shelf = Shelf.objects.create(user=self.user, name=_SHELF_NAME)
        ShelfItem.objects.create(
            shelf=shelf, collection="comics", target_id=self.comics[0].pk
        )
        self._login(self.user)

        group = _group(self._feed(self.client), _SHELF_NAME)

        assert group is not None
        hrefs = [link["href"] for link in group.get("links", [])]
        assert hrefs, group
        for param in ("filters=", "orderBy=", "orderReverse=", "topCollection="):
            assert any(param in href for href in hrefs), (param, hrefs)
        assert any(f"%5B{shelf.pk}%5D" in href for href in hrefs), hrefs

    def test_an_empty_shelf_adds_no_group(self) -> None:
        Shelf.objects.create(user=self.user, name=_SHELF_NAME)
        self._login(self.user)

        assert _group(self._feed(self.client), _SHELF_NAME) is None

    def test_other_users_and_anonymous_do_not_see_the_shelf(self) -> None:
        shelf = Shelf.objects.create(user=self.user, name=_SHELF_NAME)
        ShelfItem.objects.create(
            shelf=shelf, collection="comics", target_id=self.comics[0].pk
        )

        assert _group(self._feed(self.client), _SHELF_NAME) is None
        self._login(self.other)
        assert _group(self._feed(self.client), _SHELF_NAME) is None
