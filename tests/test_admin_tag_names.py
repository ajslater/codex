"""The tag editor's name suggestions: GET /admin/tag-names/<field>."""

from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import Imprint, Publisher, Series, Volume
from codex.models.named import Character, CreditPerson, Genre, StoryArc
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-F043"  # noqa: S105
_URL: Final = "/api/v4/admin/tag-names/"


class AdminTagNamesTestCase(TestCase):
    """Suggestions are allowlisted, prefix-first, scoped, deduped and capped."""

    @override
    def setUp(self) -> None:
        init_admin_flags()
        dc = Publisher.objects.create(name="DC Comics")
        unlimited = Publisher.objects.create(name="Comics Unlimited")
        marvel = Publisher.objects.create(name="Marvel")
        # The importer's default imprint has a blank name.
        Imprint.objects.create(name="", publisher=dc)
        vertigo = Imprint.objects.create(name="Vertigo", publisher=dc)
        Imprint.objects.create(name="Max", publisher=marvel)
        unlimited_vertigo = Imprint.objects.create(name="Vertigo", publisher=unlimited)
        sandman = Series.objects.create(name="Sandman", imprint=vertigo, publisher=dc)
        Series.objects.create(
            name="Sandman", imprint=unlimited_vertigo, publisher=unlimited
        )
        lucifer = Series.objects.create(name="Lucifer", imprint=vertigo, publisher=dc)
        for name in (1989, 2014, 999, None):
            Volume.objects.create(
                name=name, series=sandman, imprint=vertigo, publisher=dc
            )
        Volume.objects.create(name=2000, series=lucifer, imprint=vertigo, publisher=dc)
        admin = User.objects.create_user(
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _get(self, field: str, **params) -> dict:
        response = self.client.get(_URL + field, params)
        assert response.status_code == HTTPStatus.OK, response.content
        return response.json()["data"]

    def _names(self, field: str, **params) -> list:
        return self._get(field, **params)["names"]

    def test_non_staff_is_forbidden(self) -> None:
        user = User.objects.create_user(username="reader", password=_TEST_PASSWORD)
        client = Client()
        client.force_login(user)
        response = client.get(_URL + "publisher")
        assert response.status_code == HTTPStatus.FORBIDDEN, response.content

    def test_unknown_field_is_a_404(self) -> None:
        for field in ("password", "credits__person", "story_arc_numbers"):
            response = self.client.get(_URL + field)
            assert response.status_code == HTTPStatus.NOT_FOUND, field

    def test_empty_query_lists_every_name_case_insensitively(self) -> None:
        data = self._get("publisher")
        assert data == {
            "field": "publisher",
            "names": ["Comics Unlimited", "DC Comics", "Marvel"],
            "complete": True,
        }

    def test_prefix_matches_sort_first(self) -> None:
        """A name starting with the query sorts before one only containing it."""
        assert self._names("publisher", q="comics") == [
            "Comics Unlimited",
            "DC Comics",
        ]

    def test_like_wildcards_match_literally(self) -> None:
        Genre.objects.create(name="100% Pure")
        Genre.objects.create(name="100 Pure")
        Genre.objects.create(name="snake_case")
        Genre.objects.create(name="snakeXcase")
        assert self._names("genres", q="%") == ["100% Pure"]
        assert self._names("genres", q="e_c") == ["snake_case"]

    def test_blank_imprint_name_excluded(self) -> None:
        assert "" not in self._names("imprint")

    def test_series_names_deduped_across_imprints(self) -> None:
        assert self._names("series") == ["Lucifer", "Sandman"]

    def test_imprint_scoped_by_publisher(self) -> None:
        assert self._names("imprint", publisher="Marvel") == ["Max"]
        assert self._names("imprint") == ["Max", "Vertigo"]

    def test_blank_scope_is_global(self) -> None:
        assert self._names("imprint", publisher="") == ["Max", "Vertigo"]

    def test_series_scoped_by_publisher_and_imprint(self) -> None:
        imprint = Imprint.objects.select_related("publisher").get(
            name="Vertigo", publisher__name="Comics Unlimited"
        )
        Series.objects.create(
            name="Hellblazer", imprint=imprint, publisher=imprint.publisher
        )
        assert self._names(
            "series", publisher="Comics Unlimited", imprint="Vertigo"
        ) == ["Hellblazer", "Sandman"]
        assert self._names("series", publisher="DC Comics", imprint="Vertigo") == [
            "Lucifer",
            "Sandman",
        ]

    def test_volume_scoped_by_series(self) -> None:
        # Numeric order, not text order.
        assert self._names("volume", series="Sandman") == [999, 1989, 2014]
        assert self._names("volume", series="Lucifer") == [2000]

    def test_volume_integer_names_match_a_prefix(self) -> None:
        """Integers stay integers; the null volume never appears."""
        assert self._names("volume", q="20") == [2000, 2014]
        assert None not in self._names("volume")

    def test_incomplete_when_matches_exceed_the_limit(self) -> None:
        for name in ("Batman", "Batgirl", "Robin"):
            Character.objects.create(name=name)
        with patch("codex.views.admin.tagnames.LIMIT", 2):
            data = self._get("characters")
            assert data["names"] == ["Batgirl", "Batman"]
            assert data["complete"] is False
            data = self._get("characters", q="bat")
            assert data["names"] == ["Batgirl", "Batman"]
            assert data["complete"] is True

    def test_credits_are_person_names(self) -> None:
        CreditPerson.objects.create(name="Neil Gaiman")
        assert self._names("credits", q="gai") == ["Neil Gaiman"]

    def test_story_arcs_are_story_arc_names(self) -> None:
        StoryArc.objects.create(name="The Kindly Ones")
        assert self._names("story_arcs") == ["The Kindly Ones"]

    def test_query_longer_than_a_name_is_a_400(self) -> None:
        response = self.client.get(_URL + "publisher", {"q": "x" * 200})
        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
