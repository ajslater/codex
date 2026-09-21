"""
The OPDS Progression endpoint is not an existence oracle.

``GET /opds/v2.0/comics/<pk>/position`` has always gone through the ACL
seam, but the ``PUT`` resolved ``page_count`` off an unfiltered
``Comic.objects.filter(pk=...)``. The ``None`` return becomes a 404 and
anything else a 200, so an unauthenticated-for-this-library caller could
walk the pk space and learn exactly which comics exist -- and the write
itself landed on the bookmark queue with the raw URL pk.

The relaxation that survives is deliberate and pinned here too: the
pending-delete half of the ACL stays off for the write, so a position
recorded while the file is away still lands. Writes land, reads hide.
"""

import json
import shutil
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from codex.librarian.bookmark.tasks import BookmarkUpdateTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.auth import GroupAuth
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_QUEUE_PATCH: Final = "codex.views.bookmark.LIBRARIAN_QUEUE"
_PROGRESSION_MIME: Final = "application/opds-progression+json"
_TMP_DIR: Final = Path("/tmp/codex.tests.progression_acl")  # noqa: S108
_OPEN_DIR: Final = _TMP_DIR / "open"
_PRIVATE_DIR: Final = _TMP_DIR / "private"
_HTTP_OK: Final = 200
_HTTP_NOT_FOUND: Final = 404
_HTTP_NO_CONTENT: Final = 204
_PAGE_COUNT: Final = 11
#: 0.5 over a 0..10 page span.
_MID_PAGE: Final = 5


class OPDS2ProgressionACLTestCase(TestCase):
    """Both verbs answer the same way for a comic the caller can't reach."""

    @override
    def setUp(self) -> None:
        """Seed a visible comic and one behind a group the user isn't in."""
        cache.clear()
        init_admin_flags()
        for path in (_OPEN_DIR, _PRIVATE_DIR):
            path.mkdir(exist_ok=True, parents=True)

        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        self.groups = (  # pyright: ignore[reportUninitializedInstanceVariable]
            publisher,
            imprint,
            series,
            Volume.objects.create(
                name="2024", series=series, imprint=imprint, publisher=publisher
            ),
        )

        self.comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            Library.objects.create(path=str(_OPEN_DIR)), _OPEN_DIR, "open"
        )

        private_library = Library.objects.create(path=str(_PRIVATE_DIR))
        readers = Group.objects.create(name="readers")
        GroupAuth.objects.create(group=readers)
        private_library.groups.add(readers)
        self.private_comic = self._make_comic(  # pyright: ignore[reportUninitializedInstanceVariable]
            private_library, _PRIVATE_DIR, "private"
        )

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="progression", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _make_comic(self, library, dir_path: Path, name: str) -> Comic:
        """Create a Comic row backed by a touch file."""
        path = dir_path / f"{name}.cbz"
        path.touch()
        publisher, imprint, series, volume = self.groups
        return Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name=name,
            publisher=publisher,
            imprint=imprint,
            series=series,
            volume=volume,
            page_count=_PAGE_COUNT,
            size=42,
        )

    @staticmethod
    def _url(comic) -> str:
        return f"/opds/v2.0/comics/{comic.pk}/position"

    def _put(self, comic, progression: float = 0.5):
        return self.client.put(
            self._url(comic),
            data=json.dumps({"progression": progression}),
            content_type=_PROGRESSION_MIME,
        )

    @staticmethod
    def _bookmark_tasks(mock_queue) -> list:
        return [
            call.args[0]
            for call in mock_queue.put.call_args_list
            if isinstance(call.args[0], BookmarkUpdateTask)
        ]

    @patch(_QUEUE_PATCH)
    def test_a_reachable_comic_accepts_the_position(self, mock_queue) -> None:
        """The baseline the ACL must not break."""
        assert self._put(self.comic).status_code == _HTTP_OK
        tasks = self._bookmark_tasks(mock_queue)
        assert [t.comic_pks for t in tasks] == [(self.comic.pk,)], tasks
        assert tasks[0].updates == {"page": _MID_PAGE}

    @patch(_QUEUE_PATCH)
    def test_an_unreachable_comic_is_not_written(self, mock_queue) -> None:
        """A PUT to a library the caller can't browse is a 404, not a write."""
        assert self._put(self.private_comic).status_code == _HTTP_NOT_FOUND
        assert not self._bookmark_tasks(mock_queue)

    def test_the_put_does_not_leak_existence(self) -> None:
        """
        A real private comic and a pk that was never used answer alike.

        That identity is the whole point: any divergence is the oracle.
        """
        missing_pk = Comic.objects.order_by("-pk").values_list("pk", flat=True)[0] + 100
        real = self._put(self.private_comic)
        fake = self.client.put(
            f"/opds/v2.0/comics/{missing_pk}/position",
            data=json.dumps({"progression": 0.5}),
            content_type=_PROGRESSION_MIME,
        )
        assert real.status_code == fake.status_code == _HTTP_NOT_FOUND

    def test_the_get_hides_an_unreachable_comic(self) -> None:
        """The read half of the same seam, for contrast with the write."""
        assert self.client.get(self._url(self.comic)).status_code == _HTTP_NO_CONTENT
        assert (
            self.client.get(self._url(self.private_comic)).status_code
            == _HTTP_NOT_FOUND
        )

    @patch(_QUEUE_PATCH)
    def test_a_stamped_comic_still_accepts_the_position(self, mock_queue) -> None:
        """
        ``include_missing=True`` survives the fix.

        A comic whose file went away is hidden from listings for the
        retention window but must still record where the reader got to,
        or the position is lost exactly when it matters most.
        """
        Comic.objects.filter(pk=self.comic.pk).update(missing_since=timezone.now())
        assert self._put(self.comic).status_code == _HTTP_OK
        tasks = self._bookmark_tasks(mock_queue)
        assert [t.comic_pks for t in tasks] == [(self.comic.pk,)], tasks
