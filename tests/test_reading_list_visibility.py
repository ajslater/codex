"""
Who sees which entries of a reading list, and what the API refuses.

An entry shows when it is not hidden and its comic, if any, is one the
viewer may see. A missing issue shows to everyone who sees the list. The
entries view, export and copy all follow that rule. Bad input is a 400.
"""

import json
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from comicbox.readinglists import loads
from django.contrib.auth.models import Group, User
from django.core.cache import caches
from django.test import Client

from codex.models import (
    Comic,
    Library,
    ReadingList,
    ReadingListEntry,
)
from codex.models.auth import GroupAuth
from codex.models.readinglist import ReadingListMatchTier
from tests.test_reading_lists import TMP_DIR, ReadingListFixture

_PW: Final = "test-pw-hush-S106"
_OK: Final = 200
_CREATED: Final = 201
_BAD_REQUEST: Final = 400
_NOT_FOUND: Final = 404
_LISTS: Final = "/api/v4/reading-lists"
_ADMIN: Final = "/api/v4/admin/reading-lists"
_HIDDEN_NAME: Final = "Hidden Civil War 5"


def _data(response):
    body = response.json()
    return body.get("data", body) if isinstance(body, dict) else body


def _post(client: Client, url: str, body: dict):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def _patch(client: Client, url: str, body: dict):
    return client.patch(url, data=json.dumps(body), content_type="application/json")


class EntryVisibilityFixture(ReadingListFixture):
    """A global list holding a comic in a library nobody here may see."""

    @override
    def setUp(self) -> None:
        super().setUp()
        caches["tagging"].clear()
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_PW, is_staff=True, is_superuser=True
        )
        self.user = User.objects.create_user(username="reader", password=_PW)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.hidden = self._hidden_comic()  # pyright: ignore[reportUninitializedInstanceVariable]
        c1, c2, _, _ = self.comics
        self.reading_list = ReadingList.objects.create(name="Event")  # pyright: ignore[reportUninitializedInstanceVariable]
        rows = (
            (c1, False, "Civil War", "1"),
            (self.hidden, False, "Civil War", "5"),
            (None, False, "The Amazing Spider-Man", "532"),
            (c2, True, "Civil War", "2"),
        )
        for position, (comic, ignored, series, issue) in enumerate(rows):
            ReadingListEntry.objects.create(
                reading_list=self.reading_list,
                position=position,
                comic=comic,
                ignored=ignored,
                series_name=series,
                issue=issue,
                year=2006,
                reference={
                    "series": {"name": series},
                    "issue": {"name": issue},
                    "date": {"year": 2006},
                },
                match_tier=ReadingListMatchTier.EXACT_NAME
                if comic
                else ReadingListMatchTier.NONE,
            )
        self.client = Client()

    def _hidden_comic(self) -> Comic:
        hidden_dir = TMP_DIR / "hidden"
        hidden_dir.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(hidden_dir))
        group = Group.objects.create(name="nobody here")
        GroupAuth.objects.create(group=group)
        library.groups.add(group)
        path = Path(hidden_dir) / "h.cbz"
        path.touch()
        first = self.comics[0]
        return Comic.objects.create(
            library=library,
            path=path,
            name=_HIDDEN_NAME,
            issue_number=5,
            year=2006,
            publisher=first.publisher,
            imprint=first.imprint,
            series=first.series,
            volume=first.volume,
            size=1,
        )


class EntriesViewVisibilityTests(EntryVisibilityFixture):
    """The review screen lists only entries whose comics the editor may see."""

    def test_entries_leave_out_a_hidden_comic(self) -> None:
        """The hidden library's comic is not listed; the missing issue is."""
        self.client.force_login(self.admin)
        response = self.client.get(f"{_LISTS}/{self.reading_list.pk}/entries")
        assert response.status_code == _OK, response.content
        comics = [
            (entry["comic"] or {}).get("pk") for entry in _data(response)["entries"]
        ]
        assert self.hidden.pk not in comics
        assert None in comics


class ExportVisibilityTests(EntryVisibilityFixture):
    """Anyone who sees a list may export what they see of it."""

    def test_a_reader_exports_a_global_list(self) -> None:
        """A signed-in non-admin exports the shown entries they may see."""
        self.client.force_login(self.user)
        response = self.client.get(
            f"{_LISTS}/{self.reading_list.pk}/export", {"fmt": "cbl"}
        )
        assert response.status_code == _OK, response.content
        entries = loads(response.content).reading_list["entries"]
        issues = [str(entry["issue"]["name"]) for entry in entries]
        # Not the hidden comic's #5, nor the hidden entry's #2.
        assert issues == ["1", "532"]

    def test_another_users_list_is_not_exported(self) -> None:
        """A personal list stays its owner's."""
        other = ReadingList.objects.create(name="Theirs", user=self.admin)
        self.client.force_login(self.user)
        response = self.client.get(f"{_LISTS}/{other.pk}/export", {"fmt": "cbl"})
        assert response.status_code == _NOT_FOUND


class CopyVisibilityTests(EntryVisibilityFixture):
    """A copy holds only what the copier could see."""

    def test_a_copy_leaves_out_a_hidden_comic(self) -> None:
        """Copy to My Lists drops the comic the reader may not see."""
        self.client.force_login(self.user)
        response = _post(self.client, f"{_LISTS}/{self.reading_list.pk}/duplicate", {})
        assert response.status_code == _CREATED, response.content
        copy = ReadingList.objects.get(pk=_data(response)["pk"])
        rows = list(
            ReadingListEntry.objects.filter(reading_list=copy)
            .order_by("position")
            .values_list("comic_id", "series_name", "issue")
        )
        assert rows == [
            (self.comics[0].pk, "Civil War", "1"),
            (None, "The Amazing Spider-Man", "532"),
        ]


class InputCheckTests(EntryVisibilityFixture):
    """Bad input is refused with a 400, and the comic ACL applies."""

    def test_create_with_comics_applies_the_acl(self) -> None:
        """A new list with a hidden comic in its body gets only what they see."""
        self.client.force_login(self.user)
        response = _post(
            self.client,
            f"{_LISTS}/",
            {"name": "Mine", "comics": [self.hidden.pk, self.comics[0].pk]},
        )
        assert response.status_code == _CREATED, response.content
        comics = list(
            ReadingListEntry.objects.filter(
                reading_list_id=_data(response)["pk"]
            ).values_list("comic_id", flat=True)
        )
        assert comics == [self.comics[0].pk]

    def test_create_with_bad_pks_is_a_400(self) -> None:
        """Comic pks that are not numbers are refused, and no list is made."""
        self.client.force_login(self.user)
        response = _post(self.client, f"{_LISTS}/", {"name": "Mine", "comics": ["x"]})
        assert response.status_code == _BAD_REQUEST, response.content
        assert not ReadingList.objects.filter(name="Mine").exists()

    def test_pick_with_a_bad_comic_is_a_400(self) -> None:
        """An entry pick that names no comic pk is refused."""
        self.client.force_login(self.admin)
        entry = ReadingListEntry.objects.filter(reading_list=self.reading_list).first()
        assert entry
        response = _patch(
            self.client,
            f"{_LISTS}/{self.reading_list.pk}/entries/{entry.pk}",
            {"comic": "x"},
        )
        assert response.status_code == _BAD_REQUEST, response.content

    def test_admin_rename_to_a_taken_name_is_a_400(self) -> None:
        """Renaming a personal list onto its owner's other list is refused."""
        ReadingList.objects.create(name="Taken", user=self.admin)
        mine = ReadingList.objects.create(name="Mine", user=self.admin)
        self.client.force_login(self.admin)
        response = _patch(self.client, f"{_ADMIN}/{mine.pk}", {"name": "Taken"})
        assert response.status_code == _BAD_REQUEST, response.content

    def test_admin_private_onto_a_taken_name_is_a_400(self) -> None:
        """Making a global list private when the admin has one of that name."""
        ReadingList.objects.create(name="Event", user=self.admin)
        self.client.force_login(self.admin)
        response = _patch(
            self.client, f"{_ADMIN}/{self.reading_list.pk}", {"private": True}
        )
        assert response.status_code == _BAD_REQUEST, response.content

    def test_import_into_a_bad_list_is_a_400(self) -> None:
        """An ``into`` that is not a list pk is refused."""
        self.client.force_login(self.admin)
        with patch("codex.views.admin.reading_lists.imports.LIBRARIAN_QUEUE"):
            response = _post(
                self.client,
                f"{_ADMIN}/import",
                {"items": [{"kind": "metron_list", "ref": "5", "into": "x"}]},
            )
        assert response.status_code == _BAD_REQUEST, response.content

    def test_series_mapping_with_bad_pks_is_a_400(self) -> None:
        """A mapping whose list, entry or series is not a pk is refused."""
        self.client.force_login(self.admin)
        response = _post(
            self.client,
            f"{_ADMIN}/series-mappings",
            {"list": "x", "entry": "y", "series": "z"},
        )
        assert response.status_code == _BAD_REQUEST, response.content


class SuggestionVisibilityTests(EntryVisibilityFixture):
    """A missing issue is seen by all, its suggestion only by who may see it."""

    def _suggested(self, comic) -> dict | None:
        ReadingListEntry.objects.filter(
            reading_list=self.reading_list, comic__isnull=True
        ).update(suggested_comic=comic, needs_review=True)
        self.client.force_login(self.admin)
        response = self.client.get(f"{_LISTS}/{self.reading_list.pk}/entries")
        assert response.status_code == _OK, response.content
        (missing,) = (
            entry for entry in _data(response)["entries"] if not entry["comic"]
        )
        return missing["suggestedComic"]

    def test_a_hidden_comic_is_not_suggested(self) -> None:
        assert self._suggested(self.hidden) is None

    def test_a_visible_comic_is_suggested(self) -> None:
        suggested = self._suggested(self.comics[2])
        assert suggested
        assert suggested["pk"] == self.comics[2].pk
