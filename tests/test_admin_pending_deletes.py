"""
The admin surface for pending deletes.

The only window onto this state. The visibility filter hides a stamped
row from every browsing surface with no staff exemption, so without
these endpoints an admin could not tell what is being held, could not
put one back, and could not force an early delete. Every assertion here
therefore goes through the unfiltered admin API rather than a browse.
"""

import shutil
from datetime import timedelta
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from codex.librarian.pending_deletes import PENDING_DELETE_WINDOW
from codex.models import (
    Comic,
    Folder,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TMP_DIR = tmp_dir("codex.tests.pending_deletes_admin")
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_FORBIDDEN: Final = 403
_HTTP_NOT_FOUND: Final = 404


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


class AdminPendingDeletesTestCase(TestCase):
    """List and revive."""

    @override
    def setUp(self) -> None:
        """One library, one folder, two comics."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        self.folder = Folder.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in (1, 2):
            path = TMP_DIR / f"c{n}.cbz"
            path.touch()
            self.comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=n,
                    name=f"C{n}",
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    parent_folder=self.folder,
                    size=42,
                )
            )
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.plain = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="plain", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.admin)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    @staticmethod
    def _stamp(model, pk, *, hours_ago: int = 0):
        when = timezone.now() - timedelta(hours=hours_ago)
        model.objects.filter(pk=pk).update(missing_since=when)
        return when

    def _list(self):
        response = self.client.get("/api/v4/admin/pending-deletes")
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def test_nothing_pending_is_an_empty_list(self) -> None:
        """The overwhelming majority of installs, and the panel stays hidden."""
        assert self._list() == []

    def test_a_stamped_comic_is_listed(self) -> None:
        """What the panel renders."""
        comic = self.comics[0]
        when = self._stamp(Comic, comic.pk)

        rows = self._list()

        assert len(rows) == 1
        row = rows[0]
        assert row["pk"] == comic.pk
        assert row["collection"] == "comics"
        assert row["path"] == str(comic.path)
        # Computed server-side so one definition of the window exists.
        reap_after = timezone.datetime.fromisoformat(row["reapAfter"])
        assert reap_after - when == PENDING_DELETE_WINDOW

    def test_comics_and_folders_share_one_list(self) -> None:
        """Two models, one panel -- which is why this is not a JSON:API resource."""
        self._stamp(Comic, self.comics[0].pk)
        self._stamp(Folder, self.folder.pk)

        collections = {row["collection"] for row in self._list()}

        assert collections == {"comics", "folders"}

    def test_revive_clears_the_stamp(self) -> None:
        """The answer to "I know it is coming back, stop counting down"."""
        comic = self.comics[0]
        self._stamp(Comic, comic.pk)

        response = self.client.post(
            f"/api/v4/admin/pending-deletes/comics/{comic.pk}/revive"
        )

        assert response.status_code == _HTTP_OK, response.content
        comic.refresh_from_db()
        assert comic.missing_since is None
        assert self._list() == []

    def test_revive_needs_the_collection_too(self) -> None:
        """
        A comic and a folder can share a pk.

        So the pk alone does not identify a row, and the client sends
        the collection back with it.
        """
        self._stamp(Folder, self.folder.pk)
        comic_pk_absent_from_pending = self.comics[0].pk

        response = self.client.post(
            f"/api/v4/admin/pending-deletes/comics/{comic_pk_absent_from_pending}/revive"
        )

        assert response.status_code == _HTTP_NOT_FOUND
        self.folder.refresh_from_db()
        assert self.folder.missing_since is not None

    def test_reviving_a_live_row_is_a_404(self) -> None:
        """Nothing to revive is not a silent success."""
        response = self.client.post(
            f"/api/v4/admin/pending-deletes/comics/{self.comics[0].pk}/revive"
        )
        assert response.status_code == _HTTP_NOT_FOUND

    def test_an_unknown_collection_is_a_404(self) -> None:
        """Only Comic and Folder can ever carry a stamp."""
        response = self.client.post("/api/v4/admin/pending-deletes/publishers/1/revive")
        assert response.status_code == _HTTP_NOT_FOUND

    def test_a_non_admin_cannot_read_the_list(self) -> None:
        """Paths are library contents; this is an admin surface."""
        self._stamp(Comic, self.comics[0].pk)
        self.client.force_login(self.plain)

        response = self.client.get("/api/v4/admin/pending-deletes")

        assert response.status_code == _HTTP_FORBIDDEN

    def test_a_non_admin_cannot_revive(self) -> None:
        """Nor write."""
        comic = self.comics[0]
        self._stamp(Comic, comic.pk)
        self.client.force_login(self.plain)

        response = self.client.post(
            f"/api/v4/admin/pending-deletes/comics/{comic.pk}/revive"
        )

        assert response.status_code == _HTTP_FORBIDDEN
        comic.refresh_from_db()
        assert comic.missing_since is not None


class AdminLibraryMissingCountTestCase(TestCase):
    """The per-library column."""

    @override
    def setUp(self) -> None:
        """One library with two comics."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in (1, 2):
            path = TMP_DIR / f"lib{n}.cbz"
            path.touch()
            self.comics.append(
                Comic.objects.create(
                    library=self.library,
                    path=path,
                    issue_number=n,
                    name=f"L{n}",
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    size=42,
                )
            )
        admin = User.objects.create_user(
            username="admin2", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _missing_count(self) -> int:
        response = self.client.get("/api/v4/admin/libraries")
        assert response.status_code == _HTTP_OK, response.content
        body = response.json()
        rows = body.get("data", body)
        row = rows[0]
        attributes = row.get("attributes", row)
        return attributes["missingCount"]

    def test_counts_only_the_stamped_rows(self) -> None:
        """Zero on a healthy library, so the column stays hidden."""
        assert self._missing_count() == 0
        Comic.objects.filter(pk=self.comics[0].pk).update(missing_since=timezone.now())
        assert self._missing_count() == 1
