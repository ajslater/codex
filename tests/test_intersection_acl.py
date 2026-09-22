"""
Collection-row intersections obey the caller's comic ACL.

A table-view collection row summarizes its child comics: a cell shows a
value only when *every* child agrees on it. "Every child" has to mean
every child **that caller may see**, or a row leaks the shape of library
content the caller cannot browse to -- and, more visibly, blanks cells
that every comic the caller can actually see agrees on.

The rule is enforced in two spellings that must not drift:

* the ORM aggregations in :mod:`codex.views.browser.intersections`, and
* the correlated raw-SQL sort keys in the same module, which have no
  queryset to hang a ``Q`` on.

:class:`~codex.views.auth.ComicACL` is the single definition behind
both, so these tests pin the two spellings against each other as well as
pinning the end-to-end behaviour.

The other half of the rule is that a cell's *numerator* and its
``total_count`` *denominator* move together. Filtering one side alone
does not narrow a cell, it empties it: the intersection test is
"shared by N of N children", so an unfiltered denominator no child can
reach blanks every cell in the table.
"""

import shutil
from typing import Final, override

from comicbox.enums.metroninfo import MetronAgeRatingEnum
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase

from codex.models import (
    AgeRating,
    AgeRatingMetron,
    Comic,
    Folder,
    Genre,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.models.auth import GroupAuth, UserAuth
from codex.startup import init_admin_flags
from codex.views.auth import ComicACL
from codex.views.browser.intersections import (
    compute_collection_intersections,
    m2m_intersection_sort_expr,
    scalar_intersection_sort_expr,
)
from tests.tmp_dirs import tmp_dir

TMP_DIR: Final = tmp_dir("codex.tests.intersection_acl")
_OPEN_DIR: Final = TMP_DIR / "open"
_PRIVATE_DIR: Final = TMP_DIR / "private"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_VISIBLE_YEAR: Final = 2000

# Every collection model whose intersection subquery correlates on a
# Comic FK, plus Folder, whose correlation runs through the ancestor
# ``folders`` M2M and therefore builds a different SQL shape.
_CORRELATED_MODELS: Final = (Publisher, Imprint, Series, Volume, Folder)
# Both M2M sort-key shapes: the seven simple ``name`` columns share one
# builder, the five composite ones have their own.
_M2M_SORT_COLUMNS: Final = (
    "characters",
    "genres",
    "locations",
    "series_groups",
    "stories",
    "tags",
    "teams",
    "credits",
    "identifiers",
    "reprints",
    "story_arcs",
    "universes",
)
# A direct Comic column and an FK-to-name column -- the two scalar
# templates.
_SCALAR_SORT_COLUMNS: Final = ("year", "country")


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class IntersectionACLFixture(TestCase):
    """
    Two series, one of them spanning a library the test user cannot see.

    * Series **Alpha** -- one comic in the open library (2000, genre
      ``Zeta``) and one in a group-restricted library (1999, genre
      ``Alpha``).
    * Series **Beta** -- one comic in the open library (2000, genre
      ``Alpha``).

    The two series disagree on their visible genre, so a genre-ordered
    browse also discriminates the raw-SQL sort path.
    """

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        for path in (_OPEN_DIR, _PRIVATE_DIR):
            path.mkdir(exist_ok=True, parents=True)
        self.open_library = Library.objects.create(path=str(_OPEN_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.private_library = Library.objects.create(path=str(_PRIVATE_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.readers = Group.objects.create(name="readers")  # pyright: ignore[reportUninitializedInstanceVariable]
        GroupAuth.objects.create(group=self.readers)
        self.private_library.groups.add(self.readers)

        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.alpha = self._make_series("Alpha")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.beta = self._make_series("Beta")  # pyright: ignore[reportUninitializedInstanceVariable]

        self._make_comic(self.alpha, "a-open", self.open_library, 2000, "Zeta")
        self._make_comic(self.alpha, "a-priv", self.private_library, 1999, "Alpha")
        self._make_comic(self.beta, "b-open", self.open_library, 2000, "Alpha")

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="isect-reader", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _make_series(self, name: str) -> Series:
        return Series.objects.create(
            name=name, imprint=self.imprint, publisher=self.publisher
        )

    def _make_comic(
        self,
        series: Series,
        stem: str,
        library: Library,
        year: int,
        genre_name: str,
        age_rating: AgeRating | None = None,
    ) -> Comic:
        root = _OPEN_DIR if library is self.open_library else _PRIVATE_DIR
        path = root / f"{stem}.cbz"
        path.touch()
        volume, _ = Volume.objects.get_or_create(
            name=year, series=series, imprint=self.imprint, publisher=self.publisher
        )
        comic = Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=stem,
            publisher=self.publisher,
            imprint=self.imprint,
            series=series,
            volume=volume,
            size=1,
            year=year,
            page_count=1,
            age_rating=age_rating,
        )
        genre, _ = Genre.objects.get_or_create(name=genre_name)
        comic.genres.set([genre])
        return comic

    @staticmethod
    def _age_rating(name: str) -> AgeRating:
        rating = AgeRating(name=name)
        rating.presave()
        rating.save()
        return rating

    def _browse_rows(self, order_by: str = "sort_name") -> list[dict]:
        url = (
            f"/api/v4/browse/publishers/{self.publisher.pk}?page=1&viewMode=table"
            f"&columns=cover,name,year,genres&orderBy={order_by}"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)["rows"]

    def _row(self, name: str) -> dict:
        rows = self._browse_rows()
        matches = [row for row in rows if row.get("name") == name]
        assert matches, rows
        return matches[0]


class IntersectionACLCellsTestCase(IntersectionACLFixture):
    """The cell values a collection row displays."""

    def test_cells_summarize_only_visible_comics(self) -> None:
        """
        The restricted library's comic contributes nothing to Alpha's row.

        Before the ACL reached these aggregates both cells came back
        empty: the private 1999/``Alpha`` comic disagreed with the
        visible 2000/``Zeta`` one, and disagreement is what blanks an
        intersection cell.
        """
        row = self._row("Alpha")
        assert row["year"] == _VISIBLE_YEAR, row
        assert row["genres"] == ["Zeta"], row

    def test_group_member_sees_the_union(self) -> None:
        """
        A user inside the group sees both comics, so the cells go blank.

        The mirror image of the case above, and the assertion that keeps
        it honest: the cells are empty *because of* who is asking, not
        because something else in the pipeline drops the comic.
        """
        self.user.groups.add(self.readers)
        cache.clear()
        row = self._row("Alpha")
        assert row["year"] is None, row
        assert row["genres"] == [], row

    def test_age_rating_ceiling_narrows_the_cells(self) -> None:
        """
        The rating half of the ACL applies too, inside a single library.

        Series Beta lives entirely in the open library, so only the
        rating ceiling can exclude the comic added here -- which isolates
        the age-rating clause from the library-group one.
        """
        self._make_comic(
            self.beta,
            "b-mature",
            self.open_library,
            1977,
            "Horror",
            self._age_rating(MetronAgeRatingEnum.MATURE.value),
        )
        teen = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.update_or_create(
            user=self.user, defaults={"age_rating_metron": teen}
        )
        cache.clear()
        row = self._row("Beta")
        assert row["year"] == _VISIBLE_YEAR, row
        assert row["genres"] == ["Alpha"], row

    def test_m2m_sort_key_ranks_by_visible_comics(self) -> None:
        """
        The raw-SQL sort key is built over the same comics as the cells.

        Alpha's visible genre is ``Zeta`` and Beta's is ``Alpha``, so a
        genre-ordered browse puts Beta first. Unfiltered, Alpha's two
        comics share no genre at all, its sort key collapses to the
        empty string, and it sorts first instead.
        """
        names = [row.get("name") for row in self._browse_rows(order_by="genres")]
        assert names == ["Beta", "Alpha"], names


class IntersectionACLSpellingsTestCase(IntersectionACLFixture):
    """The ``Q`` and the SQL fragment stay the same predicate."""

    def test_sql_binds_pks_instead_of_interpolating_them(self) -> None:
        """Library pks travel as bound parameters, never inside the statement."""
        acl = ComicACL.for_user(self.user)
        fragment, params = acl.sql("c")
        assert fragment.count("%s") == len(params)
        assert set(acl.library_pks) <= set(params)
        assert params[: len(acl.library_pks)] == acl.library_pks

    def test_sql_and_q_select_the_same_comics(self) -> None:
        """Both spellings admit exactly one comic set, for every kind of user."""
        member = User.objects.create_user(username="isect-member")
        member.groups.add(self.readers)
        for user in (self.user, member):
            acl = ComicACL.for_user(user)
            fragment, params = acl.sql("c")
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT c.id FROM codex_comic c WHERE {fragment}",  # noqa: S608
                    params,
                )
                raw_pks = {row[0] for row in cursor.fetchall()}
            orm_pks = set(
                Comic.objects.filter(acl.q(Comic)).values_list("pk", flat=True)
            )
            assert raw_pks == orm_pks, user

    def test_empty_visible_set_admits_nothing(self) -> None:
        """No visible libraries is a false predicate, not an empty ``IN ()``."""
        acl = ComicACL(library_pks=(), max_idx=5, default_fits=True)
        fragment, params = acl.sql("c")
        assert params == ()
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM codex_comic c WHERE {fragment}"  # noqa: S608
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == 0
        assert not Comic.objects.filter(acl.q(Comic)).exists()

    def test_acl_does_not_drive_the_correlated_subquery_index(self) -> None:
        """
        The correlation column stays the access path inside the subquery.

        The composite ``(library_id, age_rating_metron_index)`` index is
        right for the outer browse query and wrong inside a correlated
        subquery, where it makes each evaluation scan every visible comic
        rather than the one collection's slice. The unary ``+`` is what
        keeps the planner off it.
        """
        acl = ComicACL.for_user(self.user)
        fragment, _ = acl.sql("c")
        assert "+c.library_id IN" in fragment


class IntersectionACLBuildersTestCase(IntersectionACLFixture):
    """Numerator and denominator carry the same ACL, in every builder."""

    def test_every_sort_builder_filters_both_sides(self) -> None:
        """
        Each builder binds the ACL twice: once for ``c``, once for ``c2``.

        ``c`` is the numerator's comic alias and ``c2`` the denominator's,
        and the intersection ``HAVING`` compares one against the other.
        A builder that filtered only the numerator would not narrow its
        cells, it would empty them.
        """
        acl = ComicACL.for_user(self.user)
        expected = (*acl.sql("c")[1], *acl.sql("c2")[1])
        columns = (
            *((col, m2m_intersection_sort_expr) for col in _M2M_SORT_COLUMNS),
            *((col, scalar_intersection_sort_expr) for col in _SCALAR_SORT_COLUMNS),
        )
        for model in _CORRELATED_MODELS:
            for column, builder in columns:
                expr = builder(model, column, acl)
                assert expr is not None, (model, column)
                assert tuple(expr.params) == expected, (model, column)

    def test_orm_aggregations_filter_both_sides(self) -> None:
        """
        The batched ORM path narrows its cells rather than emptying them.

        ``_isect_comic_count`` -- the denominator -- is annotated onto
        the same filtered queryset the per-column aggregates come from,
        so a non-empty cell here is itself the proof the two agree.
        """
        acl = ComicACL.for_user(self.user)
        isect = compute_collection_intersections(
            Series.objects.filter(pk=self.alpha.pk), ("year", "genres"), acl
        )
        assert isect[self.alpha.pk]["year"] == _VISIBLE_YEAR, isect
        assert isect[self.alpha.pk]["genres"] == ["Zeta"], isect

    def test_folder_rows_respect_the_acl(self) -> None:
        """
        Folder correlates through the ancestor M2M and needs its own proof.

        A folder's comics all share its library, so only the rating half
        of the ACL can split them -- which is the half the Folder branch
        would otherwise be least likely to have.
        """
        folder = Folder.objects.create(library=self.open_library, path=str(_OPEN_DIR))
        visible = Comic.objects.get(name="a-open")
        hidden = self._make_comic(
            self.alpha,
            "a-mature",
            self.open_library,
            1977,
            "Horror",
            self._age_rating(MetronAgeRatingEnum.MATURE.value),
        )
        for comic in (visible, hidden):
            comic.folders.set([folder])
        teen = AgeRatingMetron.objects.get(name=MetronAgeRatingEnum.TEEN.value)
        UserAuth.objects.update_or_create(
            user=self.user, defaults={"age_rating_metron": teen}
        )
        cache.clear()
        acl = ComicACL.for_user(self.user)
        isect = compute_collection_intersections(
            Folder.objects.filter(pk=folder.pk), ("year", "genres"), acl
        )
        assert isect[folder.pk]["year"] == _VISIBLE_YEAR, isect
        assert isect[folder.pk]["genres"] == ["Zeta"], isect
