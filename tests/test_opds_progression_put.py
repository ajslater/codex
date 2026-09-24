"""
OPDS Progression 1.0 ``PUT``: document on success, Problem Details on error.

The draft answers a successful update with the Progression Document and
every error but 401 with an RFC 7807 Problem Details object carrying a
``type`` and ``title``. The document's ``modified`` must be the stored
one: a client echoes it on its next conditional ``PUT``, and a fabricated
timestamp earlier than the stored row would be a spurious 409.
"""

import json
from datetime import timedelta
from typing import Final, override

from django.utils import timezone

from codex.models import Bookmark, Comic
from tests.opds_schema import validate_opds_progression
from tests.test_opds_progression_acl import (
    _MID_PAGE,
    _MID_PROGRESSION,
    _PROGRESSION_MIME,
    ProgressionSeedTestCase,
)

_PROBLEM_MIME: Final = "application/problem+json"
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
_HTTP_NOT_FOUND: Final = 404
_HTTP_CONFLICT: Final = 409
_INVALID_PAYLOAD_TYPE: Final = (
    "https://registry.opds.io/error#progression-invalid-payload"
)
_INVALID_PAYLOAD_TITLE: Final = (
    "Progression could not be updated due to an invalid payload."
)
_CONFLICT_TYPE: Final = "https://registry.opds.io/error#progression-date"
_CONFLICT_TITLE: Final = "A more recent progression point is already available."


class OPDS2ProgressionPutTestCase(ProgressionSeedTestCase):
    """The PUT half of the Progression endpoint, as the logged-in user."""

    @override
    def setUp(self) -> None:
        """Seed the fixture, then take the user's identity."""
        super().setUp()
        self.client.force_login(self.user)

    def _put_document(self, document: dict, comic=None):
        return self.client.put(
            self._url(comic or self.comic),
            data=json.dumps(document),
            content_type=_PROGRESSION_MIME,
        )

    @staticmethod
    def _assert_problem(response, status: int, type_uri: str, title: str) -> None:
        assert response.status_code == status, response.content
        assert response.headers["Content-Type"].startswith(_PROBLEM_MIME)
        assert response.json() == {"type": type_uri, "title": title}

    def _assert_document(self, response, progression: float) -> dict:
        assert response.status_code == _HTTP_OK, response.content
        data = response.json()
        assert not validate_opds_progression(data), validate_opds_progression(data)
        assert data["progression"] == progression
        return data

    def test_put_with_invalid_progression_has_problem_details(self) -> None:
        response = self._put_document({"progression": "abc"})
        self._assert_problem(
            response, _HTTP_BAD_REQUEST, _INVALID_PAYLOAD_TYPE, _INVALID_PAYLOAD_TITLE
        )

    def test_put_without_progression_has_problem_details(self) -> None:
        response = self._put_document({})
        self._assert_problem(
            response, _HTTP_BAD_REQUEST, _INVALID_PAYLOAD_TYPE, _INVALID_PAYLOAD_TITLE
        )

    def test_put_and_get_unreachable_comic_have_problem_details(self) -> None:
        put = self._put_document({"progression": 0.5}, self.private_comic)
        assert put.status_code == _HTTP_NOT_FOUND
        assert put.headers["Content-Type"].startswith(_PROBLEM_MIME)
        get = self.client.get(self._url(self.private_comic))
        assert get.status_code == _HTTP_NOT_FOUND
        assert get.json() == put.json()

    def test_put_stale_modified_409_has_problem_details(self) -> None:
        Bookmark.objects.create(user=self.user, comic=self.comic, page=_MID_PAGE)
        stale = (timezone.now() - timedelta(days=1)).isoformat()
        response = self._put_document({"progression": 0.1, "modified": stale})
        self._assert_problem(response, _HTTP_CONFLICT, _CONFLICT_TYPE, _CONFLICT_TITLE)
        assert Bookmark.objects.get().page == _MID_PAGE

    def test_put_success_returns_a_progression_document(self) -> None:
        response = self._put_document({"progression": _MID_PROGRESSION})
        data = self._assert_document(response, _MID_PROGRESSION)
        bookmark = Bookmark.objects.get()
        assert bookmark.page == _MID_PAGE
        assert data["title"] == f"Page {_MID_PAGE + 1}"
        get = self.client.get(self._url(self.comic)).json()
        assert data["modified"] == get["modified"]

    def test_put_conditional_update_returns_a_progression_document(self) -> None:
        bookmark = Bookmark.objects.create(user=self.user, comic=self.comic, page=1)
        old = timezone.now() - timedelta(days=1)
        Bookmark.objects.filter(pk=bookmark.pk).update(updated_at=old)
        response = self._put_document(
            {"progression": _MID_PROGRESSION, "modified": timezone.now().isoformat()}
        )
        data = self._assert_document(response, _MID_PROGRESSION)
        bookmark.refresh_from_db()
        assert bookmark.page == _MID_PAGE
        assert bookmark.updated_at > old
        get = self.client.get(self._url(self.comic)).json()
        assert data["modified"] == get["modified"]

    def test_put_then_echoed_modified_is_not_a_conflict(self) -> None:
        """First write, then echo what the server returned: never a 409."""
        first = self._put_document({"progression": 0.2}).json()
        get = self.client.get(self._url(self.comic)).json()
        assert get["modified"] == first["modified"]
        response = self._put_document(
            {"progression": _MID_PROGRESSION, "modified": get["modified"]}
        )
        self._assert_document(response, _MID_PROGRESSION)
        assert Bookmark.objects.get().page == _MID_PAGE

    def test_a_stamped_comic_put_still_returns_the_document(self) -> None:
        """Writes land, reads hide: the PUT answers even while the GET 404s."""
        Comic.objects.filter(pk=self.comic.pk).update(missing_since=timezone.now())
        response = self._put_document({"progression": _MID_PROGRESSION})
        self._assert_document(response, _MID_PROGRESSION)
        assert self.client.get(self._url(self.comic)).status_code == _HTTP_NOT_FOUND


class OPDS2ProgressionAnonPutTestCase(ProgressionSeedTestCase):
    """A session-less visitor's first PUT establishes a session and reads back."""

    def test_anonymous_put_returns_the_document_and_reads_back(self) -> None:
        response = self.client.put(
            self._url(self.comic),
            data=json.dumps({"progression": _MID_PROGRESSION}),
            content_type=_PROGRESSION_MIME,
        )
        assert response.status_code == _HTTP_OK, response.content
        assert response.json()["progression"] == _MID_PROGRESSION
        get = self.client.get(self._url(self.comic))
        assert get.status_code == _HTTP_OK
        assert get.json()["modified"] == response.json()["modified"]
