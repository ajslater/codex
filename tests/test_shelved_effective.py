"""
The ``shelved`` flag and sort follow effective shelf membership.

The flag was true only when the row itself sat on a shelf, while the
Shelves cell beside it lists the shelves a row is on directly or through a
parent, and for a collection row only the shelves every comic under it
shares. An issue of a shelved series listed the shelf and sorted with the
unshelved rows. Now a row is ``shelved`` exactly when its cell would list
at least one shelf.
"""

from typing import Final, override

from cachalot.utils import _get_tables
from django.contrib.auth.models import Group, User
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Count
from django.utils import timezone

from codex.models import Comic, Folder, Library, Series, StoryArc, Volume
from codex.models.auth import GroupAuth
from codex.models.named import StoryArcNumber
from codex.views.auth import ComicACL
from codex.views.browser.shelf_membership import annotate_shelved
from tests.shelf_fixtures import (
    HTTP_OK,
    SETTINGS_URL,
    TEST_PASSWORD,
    TMP_DIR,
    ShelfTestCase,
    items_url,
    post_json,
    v4,
)

_SHOW_ALL: Final = {
    "publishers": True,
    "imprints": True,
    "series": True,
    "volumes": True,
}


def _group_by(qs) -> list:
    """Return the GROUP BY terms the compiler emits for ``qs``."""
    return qs.query.get_compiler(DEFAULT_DB_ALIAS).pre_sql_setup()[2]


class _ShelvedTestCase(ShelfTestCase):
    """Two issues in the first chain's series, so its rows can intersect."""

    @override
    def setUp(self) -> None:
        super().setUp()
        path = TMP_DIR / "c1b.cbz"
        path.touch()
        self.c1b = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library,
            path=path,
            issue_number=3,
            name="C1b",
            publisher=self.p1,
            imprint=self.i1,
            series=self.s1,
            volume=self.v1,
            size=1,
        )

    def _flags(self, model, user=None) -> dict[int, bool]:
        user = user or self.user
        qs = annotate_shelved(model.objects.all(), user, ComicACL.for_user(user))
        return dict(qs.values_list("pk", "shelved"))


class ShelvedAnnotationTestCase(_ShelvedTestCase):
    """The annotation itself, row by row."""

    def test_a_comic_is_shelved_through_its_series(self) -> None:
        self._put(self._shelf(), "series", self.s1.pk)
        assert self._flags(Comic) == {
            self.c1.pk: True,
            self.c1b.pk: True,
            self.c2.pk: False,
        }

    def test_a_series_needs_every_comic_on_one_shelf(self) -> None:
        shelf = self._shelf("A")
        self._put(shelf, "comics", self.c1.pk)
        assert self._flags(Series)[self.s1.pk] is False
        self._put(shelf, "comics", self.c1b.pk)
        assert self._flags(Series)[self.s1.pk] is True

    def test_a_series_split_across_two_shelves_is_not_shelved(self) -> None:
        self._put(self._shelf("A"), "comics", self.c1.pk)
        self._put(self._shelf("B"), "comics", self.c1b.pk)
        assert self._flags(Series)[self.s1.pk] is False

    def test_a_series_through_its_publisher(self) -> None:
        self._put(self._shelf(), "publishers", self.p1.pk)
        assert self._flags(Series) == {self.s1.pk: True, self.s2.pk: False}

    def test_a_shelved_series_with_no_comics_is_not_shelved(self) -> None:
        """Its cell lists nothing: there is no comic to share the shelf."""
        empty = Series.objects.create(name="Empty", publisher=self.p1, imprint=self.i1)
        self._put(self._shelf(), "series", empty.pk)
        assert self._flags(Series)[empty.pk] is False

    def test_only_live_visible_comics_count(self) -> None:
        """A pending delete or a comic the user can't see doesn't spoil a row."""
        self._put(self._shelf(), "comics", self.c1.pk)
        Comic.objects.filter(pk=self.c1b.pk).update(missing_since=timezone.now())
        hidden_dir = TMP_DIR / "hidden"
        hidden_dir.mkdir(parents=True, exist_ok=True)
        hidden = Library.objects.create(path=str(hidden_dir))
        group = Group.objects.create(name="nobody here")
        GroupAuth.objects.create(group=group)
        hidden.groups.add(group)
        path = hidden_dir / "h.cbz"
        path.touch()
        Comic.objects.create(
            library=hidden,
            path=path,
            issue_number=9,
            name="Hidden",
            publisher=self.p1,
            imprint=self.i1,
            series=self.s1,
            volume=self.v1,
            size=1,
        )
        assert self._flags(Series)[self.s1.pk] is True

    def test_other_users_shelves_never_count(self) -> None:
        other = User.objects.create_user(username="other", password=TEST_PASSWORD)
        self._put(self._shelf("Theirs", user=other), "series", self.s1.pk)
        assert not any(self._flags(Comic).values())
        assert self._flags(Series, user=other)[self.s1.pk] is True

    def test_a_folder_row_through_an_ancestor_folder(self) -> None:
        top_dir = TMP_DIR / "top"
        leaf_dir = top_dir / "leaf"
        leaf_dir.mkdir(parents=True, exist_ok=True)
        top = Folder.objects.create(library=self.library, path=str(top_dir))
        leaf = Folder.objects.create(
            library=self.library, parent_folder=top, path=str(leaf_dir)
        )
        self.c1.folders.set([top, leaf])
        self._put(self._shelf(), "folders", top.pk)
        flags = self._flags(Folder)
        assert (flags[top.pk], flags[leaf.pk]) == (True, True)

    def test_an_arc_row_needs_every_comic_in_it(self) -> None:
        arc = StoryArc.objects.create(name="Arc")
        for number, comic in enumerate((self.c1, self.c2)):
            comic.story_arc_numbers.add(
                StoryArcNumber.objects.create(story_arc=arc, number=number)
            )
        shelf = self._shelf()
        self._put(shelf, "series", self.s1.pk)
        assert self._flags(StoryArc)[arc.pk] is False
        self._put(shelf, "comics", self.c2.pk)
        assert self._flags(StoryArc)[arc.pk] is True


class ShelvedCachalotTestCase(_ShelvedTestCase):
    """cachalot ties the flag to the shelf tables and still caches it."""

    def test_every_shelvable_query_depends_on_shelf_items(self) -> None:
        self._put(self._shelf("A"), "series", self.s1.pk)
        self._put(self._shelf("B"), "folders", 1)
        acl = ComicACL.for_user(self.user)
        for model in (Comic, Series, Folder, StoryArc):
            qs = annotate_shelved(model.objects.all(), self.user, acl)
            # Raises UncachableQuery if a subquery is out of cachalot's reach.
            tables = _get_tables(DEFAULT_DB_ALIAS, qs.query)
            assert "codex_shelfitem" in tables, model

    def test_the_flag_stays_out_of_group_by(self) -> None:
        """
        In GROUP BY, SQLite ran the flag once per joined comic row.

        A folders table browse, fanned out to every descendant comic,
        took 22 s cold on a 17,881-comic library.
        """
        self._put(self._shelf(), "series", self.s1.pk)
        acl = ComicACL.for_user(self.user)
        base = Folder.objects.annotate(n=Count("comic"))
        shelved = annotate_shelved(base, self.user, acl)
        assert len(_group_by(shelved)) == len(_group_by(base))


class ShelvedTableViewTestCase(_ShelvedTestCase):
    """Through the browse API: the flag agrees with the cell, and sorts."""

    @override
    def setUp(self) -> None:
        super().setUp()
        self._settings({"show": _SHOW_ALL, "viewMode": "table"})

    def _settings(self, payload: dict) -> None:
        response = post_json(self.client, "patch", SETTINGS_URL, payload)
        assert response.status_code == HTTP_OK, response.content

    def _rows(self, url: str) -> list[dict]:
        response = self.client.get(url)
        assert response.status_code == HTTP_OK, response.content
        return v4(response)["rows"]

    def _add(self, shelf_pk: int, collection: str, pk: int) -> None:
        response = post_json(
            self.client, "patch", items_url(shelf_pk), {"add": {collection: [pk]}}
        )
        assert response.status_code == HTTP_OK, response.content

    def test_the_flag_agrees_with_the_cell_at_every_level(self) -> None:
        """
        Each row is shelved exactly when its Shelves cell lists a shelf.

        A ``/browse/<collection>/<pks>`` url lists the children of those
        rows; the first chain is shelved through its series, half of it
        again on a second shelf, and the second chain not at all.
        """
        self._put(self._shelf("Series"), "series", self.s1.pk)
        self._put(self._shelf("Half"), "comics", self.c1.pk)
        urls = (
            "/api/v4/browse/publishers?page=1",
            f"/api/v4/browse/publishers/{self.p1.pk}?page=1",
            f"/api/v4/browse/imprints/{self.i1.pk}?page=1",
            f"/api/v4/browse/series/{self.s1.pk}?page=1",
            f"/api/v4/browse/volumes/{self.v1.pk}?page=1",
            f"/api/v4/browse/volumes/{self.v2.pk}?page=1",
        )
        flags = set()
        for url in urls:
            rows = self._rows(f"{url}&columns=name,shelved")
            assert rows, url
            for row in rows:
                assert row["shelved"] is bool(row["shelves"]), (url, row)
                flags.add(row["shelved"])
        assert flags == {True, False}

    def test_sorting_by_shelved_uses_effective_membership(self) -> None:
        """Neither publisher is itself on a shelf; every comic of p1 is."""
        self._put(self._shelf(), "series", self.s1.pk)
        url = "/api/v4/browse/publishers?page=1&columns=name,shelved"
        for reverse, order in ((True, (self.p1, self.p2)), (False, (self.p2, self.p1))):
            self._settings({"orderBy": "shelved", "orderReverse": reverse})
            rows = self._rows(url)
            pks_and_flags = [(row["pk"], row["shelved"]) for row in rows]
            expected = [(pub.pk, pub == self.p1) for pub in order]
            assert pks_and_flags == expected, reverse

    def test_an_inherited_flag_follows_a_membership_change(self) -> None:
        """The refetch is byte-identical SQL, so a stale cache would show."""
        shelf = self._shelf()
        self._put(shelf, "series", self.s2.pk)
        self._settings({"orderBy": "shelved"})
        comics_url = f"/api/v4/browse/volumes/{self.v1.pk}?page=1&columns=shelved"
        series_url = f"/api/v4/browse/imprints/{self.i1.pk}?page=1&columns=shelved"
        assert [row["shelved"] for row in self._rows(comics_url)] == [False, False]
        assert [row["shelved"] for row in self._rows(series_url)] == [False]
        self._add(shelf.pk, "series", self.s1.pk)
        assert [row["shelved"] for row in self._rows(comics_url)] == [True, True]
        assert [row["shelved"] for row in self._rows(series_url)] == [True]

    def test_a_merged_row_needs_every_pk_it_stands_for(self) -> None:
        """
        Volumes group by name, so ``v1`` and a same-named twin are one row.

        The grouped query selects one arbitrary pk for the row, so a flag
        correlated on it judged the row by that volume alone.
        """
        twin = Volume.objects.create(
            name=self.v1.name, publisher=self.p2, imprint=self.i2, series=self.s2
        )
        Comic.objects.filter(pk=self.c2.pk).update(volume=twin)
        url = "/api/v4/browse/series?page=1&columns=name,shelved"
        for volume in (self.v1, twin):
            shelf = self._shelf(f"Only {volume.pk}")
            self._put(shelf, "volumes", volume.pk)
            rows = [
                row for row in self._rows(url) if row["ids"] == [self.v1.pk, twin.pk]
            ]
            assert [(row["shelved"], row["shelves"]) for row in rows] == [(False, [])]
            shelf.delete()
        both = self._shelf("Both")
        self._put(both, "volumes", self.v1.pk)
        self._put(both, "volumes", twin.pk)
        rows = [row for row in self._rows(url) if row["ids"] == [self.v1.pk, twin.pk]]
        assert [(row["shelved"], row["shelves"]) for row in rows] == [(True, [both.pk])]
