"""
Operator expressions on related-name search fields filter by those names.

A column token whose expression carries an operator (``*`` inside or in
front, ``<``, ``>``, ``..``) skips full text search and becomes an ORM
lookup. ``parse_field`` resolved columns only against Comic's concrete
fields, so every many-to-many column (``characters:*man``,
``story_arcs:*War``) raised "Unknown field", and the ``story_arcs`` span
named a relation Comic doesn't have. The search filter swallows the error
and drops the term, so the browser showed every comic. Ranges (``A..T``)
never left full text search at all.
"""

import shutil
from http import HTTPStatus
from typing import Final, override
from urllib.parse import urlencode

import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import (
    Character,
    Comic,
    Credit,
    CreditPerson,
    Imprint,
    Library,
    Publisher,
    Series,
    StoryArc,
    StoryArcNumber,
    Volume,
)
from codex.startup import init_admin_flags
from codex.views.browser.filters.search.field.column import parse_field
from codex.views.browser.filters.search.parse import (
    _COMPOUND_COLUMN_MAP,
    _VALID_COLUMNS,
    _is_column_operators_used,
)
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
TMP_DIR: Final = tmp_dir("codex.tests.search_field_relations")
# Every column the search preparser can hand to the ORM field path.
_FIELD_COLUMNS: Final = tuple(
    sorted(
        _VALID_COLUMNS | {col for cols in _COMPOUND_COLUMN_MAP.values() for col in cols}
    )
)


@pytest.mark.parametrize("column", _FIELD_COLUMNS)
def test_every_search_column_resolves(column: str) -> None:
    """Each column parses into a lookup the Comic queryset accepts."""
    _, rel, _ = parse_field(column)
    if column == "issue":
        # Not a column: parse_expression splits it into number and suffix.
        rel = "issue_number"
    # Raises FieldError when the span names a missing relation.
    Comic.objects.filter(**{f"{rel}__isnull": True})


@pytest.mark.parametrize(
    ("exp", "used"),
    [
        ("*man", True),
        ("Civ*War", True),
        ("<T", True),
        ("A..T", True),
        ("Spider", False),
        ('"A..T"', False),
    ],
)
def test_column_operators_detected(exp: str, *, used: bool) -> None:
    """Operator forms leave full text search for the ORM field path."""
    # The range arm once read ``\.{(2,)}`` in an f-string, which compiles
    # to ``\.(2,)`` and never matched ``..``.
    assert _is_column_operators_used(exp) is used


@pytest.mark.parametrize(
    ("column", "many_to_many"),
    [
        ("characters", True),
        ("credits", True),
        ("story_arcs", True),
        ("identifiers", True),
        ("sources", True),
        ("alternate_series", True),
        ("role", True),
        ("series", False),
        ("age_rating_metron", False),
        ("volume_to", False),
    ],
)
def test_many_to_many_flag(column: str, *, many_to_many: bool) -> None:
    """The flag follows whether the span crosses a many-to-many relation."""
    assert parse_field(column)[2] is many_to_many


class SearchFieldRelationsTestCase(TestCase):
    """Two comics in one series that differ only by their related names."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name=2024, series=self.series, imprint=imprint, publisher=publisher
        )
        comics = []
        for issue, name in enumerate(("spider", "wolverine"), start=1):
            path = TMP_DIR / f"{name}.cbz"
            path.touch()
            comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=issue,
                    name=name,
                    publisher=publisher,
                    imprint=imprint,
                    series=self.series,
                    volume=volume,
                    size=1,
                )
            )
        self.spider, wolverine = comics  # pyright: ignore[reportUninitializedInstanceVariable]
        self._relate(self.spider, "Spider-Man", "Civil War", "Stan Lee")
        self._relate(wolverine, "Wolverine", "Secret Wars", "Chris Claremont")

        user = User.objects.create_user(
            username="search_field_relations_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    @staticmethod
    def _relate(comic: Comic, character: str, story_arc: str, person: str) -> None:
        comic.characters.add(Character.objects.create(name=character))
        arc = StoryArc.objects.create(name=story_arc)
        comic.story_arc_numbers.add(StoryArcNumber.objects.create(story_arc=arc))
        credit_person = CreditPerson.objects.create(name=person)
        comic.credits.add(Credit.objects.create(person=credit_person))

    def _search_book_pks(self, query: str) -> list[int]:
        params = urlencode({"page": 1, "q": query})
        response = self.client.get(f"/api/v4/browse/series/{self.series.pk}?{params}")
        assert response.status_code == HTTPStatus.OK, response.content
        return [book["pk"] for book in response.json()["data"]["books"]]

    def test_operator_forms_filter_by_related_names(self) -> None:
        """Suffix, comparison and range forms all reach the related names."""
        for query in (
            "characters:*man",
            "character:*pider*",
            "characters:<T",
            "characters:A..T",
            "reading_lists:*War",
            "story_arcs:*War",
            "arc:Civ*War",
            "credits:*Lee",
        ):
            assert self._search_book_pks(query) == [self.spider.pk], query

    def test_negated_operator_form_excludes(self) -> None:
        """A leading ``not`` excludes the comics whose names match."""
        wolverine_pks = self._search_book_pks("not characters:*man")
        assert self.spider.pk not in wolverine_pks
        assert len(wolverine_pks) == 1
