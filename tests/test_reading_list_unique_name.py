"""
A repeated personal list name gets a `` (N)`` that survives the name limit.

``CleaningCharField`` cuts a name to ``MAX_NAME_LEN`` before every lookup,
so a suffix past the limit was cut off again and every candidate read as
the taken name: Duplicate, an import and a restore looped forever. A guard
fails the test instead of hanging it.
"""

import json
from collections.abc import Generator
from contextlib import contextmanager
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.choices.limits import MAX_NAME_LEN
from codex.librarian.scribe.readinglists.service import unique_name
from codex.models import ReadingList

_PW: Final = "test-pw-hush-S106"
_CREATED: Final = 201
_BAD_REQUEST: Final = 400
_LISTS: Final = "/api/v4/reading-lists"
# More lookups than any of these cases needs.
_MAX_LOOKUPS: Final = 20


@contextmanager
def _bounded_lookups() -> Generator[None]:
    """Fail, rather than spin, when the name search does not end."""
    real_filter = ReadingList.objects.filter
    lookups: list[str] = []

    def counting_filter(*args, **kwargs):
        lookups.append(kwargs.get("name", ""))
        if len(lookups) > _MAX_LOOKUPS:
            reason = f"unique_name never ends; it last tried {lookups[-1]!r}"
            raise AssertionError(reason)
        return real_filter(*args, **kwargs)

    with patch.object(ReadingList.objects, "filter", side_effect=counting_filter):
        yield


class UniqueNameTests(TestCase):
    """The helper numbers a repeat within the limit."""

    @override
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]

    def test_a_long_taken_name_is_numbered_within_the_limit(self) -> None:
        """A 128-character taken name comes back cut short and numbered."""
        name = "x" * MAX_NAME_LEN
        ReadingList.objects.create(name=name, user=self.user)
        with _bounded_lookups():
            candidate = unique_name(name, self.user)
        assert len(candidate) <= MAX_NAME_LEN
        assert candidate.endswith(" (2)")
        assert not ReadingList.objects.filter(user=self.user, name=candidate).exists()

    def test_numbers_keep_counting_at_the_limit(self) -> None:
        """The second repeat of a long name is (3), still within the limit."""
        name = "y" * (MAX_NAME_LEN - 1)
        ReadingList.objects.create(name=name, user=self.user)
        with _bounded_lookups():
            second = unique_name(name, self.user)
        ReadingList.objects.create(name=second, user=self.user)
        with _bounded_lookups():
            third = unique_name(name, self.user)
        assert (second[-4:], third[-4:]) == (" (2)", " (3)")
        assert len(third) <= MAX_NAME_LEN

    def test_a_short_name_is_untouched(self) -> None:
        """A free name is kept, and a short repeat keeps all of its name."""
        assert unique_name("Mine", self.user) == "Mine"
        ReadingList.objects.create(name="Mine", user=self.user)
        assert unique_name("Mine", self.user) == "Mine (2)"


class DuplicateNameTests(TestCase):
    """Copy to My Lists of a list with a long name returns."""

    @override
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client = Client()
        self.client.force_login(self.user)
        self.original = ReadingList.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="z" * (MAX_NAME_LEN - 1), user=self.user
        )

    def _duplicate(self, body: dict):
        with _bounded_lookups():
            return self.client.post(
                f"{_LISTS}/{self.original.pk}/duplicate",
                data=json.dumps(body),
                content_type="application/json",
            )

    def test_a_long_name_duplicates_twice(self) -> None:
        """Each copy gets a name of its own within the limit."""
        names = set()
        for _ in range(2):
            response = self._duplicate({})
            assert response.status_code == _CREATED, response.content
            names.add(response.json()["data"]["name"])
        assert len(names) == 2  # noqa: PLR2004
        assert all(len(name) <= MAX_NAME_LEN for name in names)

    def test_an_overlong_name_is_refused(self) -> None:
        """A name past the limit is a 400, not a silent cut."""
        response = self._duplicate({"name": "n" * (MAX_NAME_LEN + 1)})
        assert response.status_code == _BAD_REQUEST, response.content
        assert ReadingList.objects.count() == 1

    def test_a_blank_name_is_refused(self) -> None:
        """A name of spaces is a 400."""
        response = self._duplicate({"name": "   "})
        assert response.status_code == _BAD_REQUEST, response.content
