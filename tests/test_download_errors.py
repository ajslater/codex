"""
A comic file that cannot be read is Not Found, not a server error.

Every route that hands a library file to the client used to open it
outside any guard, so a comic whose file had been moved, deleted, or
left on a mount that went away answered ``500`` with a traceback --
``FileNotFoundError`` for the missing case and ``PermissionError`` for
the unreadable one. The row is fine and the rest of the library is
fine; only this one file cannot be served, which is a 404.

The collection zip failed later and worse: ``ZipStream`` opens each
member when the generator reaches it, long after the headers have gone
out, so one unreadable comic truncated the archive *under a 200*. It now
skips what it cannot read and says how many in
``X-Codex-Skipped-Comics``.

The second half of the bug is caching. The PDF and OPDS page routes
patched ``Cache-Control: max-age=604800`` onto every response including
the 404, so a browser that saw one refused to re-request the book for a
week -- long after the file came back. ``cache_control_2xx`` marks only
success responses cacheable.

Failures are mocked rather than made with ``chmod``: CI runs as root,
where mode bits are ignored and a 0o000 file stays readable. ``io.open``
is the patch point because both ``pathlib.Path.open`` and ``zipfile``
bottom out there, and patching it leaves the ``open`` builtin -- which
the rest of the request uses -- alone.
"""

from __future__ import annotations

import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Folder, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags
from codex.views.reader._archive_cache import archive_cache, page_acl_cache

TMP_DIR: Final = Path("/tmp/codex.tests.download_errors")  # noqa: S108
_SOURCE_CBZ: Final = Path(__file__).parent / "files" / "comicbox-2-example.cbz"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_HTTP_NOT_FOUND: Final = 404
_EACCES: Final = PermissionError(13, "Permission denied")
#: ``BOOK_AGE`` / ``PAGE_MAX_AGE``, the week these routes ask for.
_WEEK: Final = "max-age=604800"

#: Captured before any patch: ``Path.open`` and ``zipfile`` both call
#: ``io.open``, so a fake that called it would recurse into itself.
_REAL_IO_OPEN = io.open


def _io_open_failing_for(targets: frozenset[Path], error: OSError):
    """Return an ``io.open`` that refuses the given paths."""

    def fake_open(file, *args, **kwargs):
        # ``io.open`` also takes a file descriptor and a bytes path;
        # neither is a target, and neither survives ``Path()``.
        name = os.fspath(file) if isinstance(file, (str, os.PathLike)) else file
        if isinstance(name, str) and Path(name) in targets:
            raise error
        return _REAL_IO_OPEN(file, *args, **kwargs)

    return fake_open


def _unreadable(*paths: Path):
    """Patch ``io.open`` so every given path answers EACCES."""
    return patch("io.open", _io_open_failing_for(frozenset(paths), _EACCES))


def _body(response) -> bytes:
    """Drain a ``FileResponse``'s stream into bytes."""
    return b"".join(response.streaming_content)


class DownloadErrorsTestCase(TestCase):
    """Two real comics in one series; each test breaks one of them."""

    @override
    def setUp(self) -> None:
        """Copy the example archive twice so both are genuinely readable."""
        cache.clear()
        # Both reader caches are process-wide and keyed on path, and the
        # paths repeat across tests. Without this a later test reads a
        # handle an earlier one opened.
        archive_cache.shutdown()
        page_acl_cache.clear()
        init_admin_flags()
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        TMP_DIR.mkdir(parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2024", series=self.series, imprint=imprint, publisher=publisher
        )
        folder = Folder.objects.create(
            library=library, path=str(TMP_DIR), name=TMP_DIR.name
        )
        self.paths: list[Path] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comics: list[Comic] = []  # pyright: ignore[reportUninitializedInstanceVariable]
        for n in (1, 2):
            path = TMP_DIR / f"c{n}.cbz"
            shutil.copy(_SOURCE_CBZ, path)
            self.paths.append(path)
            comic = Comic.objects.create(
                library=library,
                path=path,
                issue_number=n,
                name=f"C{n}",
                sort_name=f"C{n}",
                publisher=publisher,
                imprint=imprint,
                series=self.series,
                volume=volume,
                parent_folder=folder,
                size=path.stat().st_size,
                page_count=4,
            )
            comic.folders.add(folder)
            self.comics.append(comic)
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="downloader", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        """Close cached archives before the files go away."""
        archive_cache.shutdown()
        page_acl_cache.clear()
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _download_url(self, index: int = 0) -> str:
        return f"/api/v4/comics/{self.comics[index].pk}/download/c.cbz"

    def _pdf_url(self, index: int = 0) -> str:
        return f"/c/{self.comics[index].pk}/book.pdf"

    def _page_url(self, index: int = 0) -> str:
        return f"/api/v4/comics/{self.comics[index].pk}/pages/0"

    def _collection_url(self) -> str:
        return f"/api/v4/browse/series/{self.series.pk}/download/Ser.zip"

    # ── The single-comic routes ────────────────────────────────────────

    def test_a_readable_comic_still_downloads(self) -> None:
        """Sanity: the healthy case is untouched."""
        response = self.client.get(self._download_url())
        assert response.status_code == _HTTP_OK, response.status_code
        body = _body(response)
        assert body == self.paths[0].read_bytes()

    def test_a_missing_comic_file_is_not_found(self) -> None:
        """Was a 500 with a ``FileNotFoundError`` traceback."""
        self.paths[0].unlink()
        response = self.client.get(self._download_url())
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code

    def test_an_unreadable_comic_file_is_not_found(self) -> None:
        """Was a 500 with a ``PermissionError`` traceback."""
        with _unreadable(self.paths[0]):
            response = self.client.get(self._download_url())
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code

    def test_the_download_error_does_not_name_the_file(self) -> None:
        """The path belongs in the log, not in an API response."""
        with _unreadable(self.paths[0]):
            response = self.client.get(self._download_url())
        assert str(self.paths[0]) not in response.content.decode()

    # ── The week-long 404 cache ────────────────────────────────────────

    def test_a_served_pdf_is_still_cached_for_a_week(self) -> None:
        """The optimization the route exists for is not lost."""
        response = self.client.get(self._pdf_url())
        assert response.status_code == _HTTP_OK, response.status_code
        _body(response)
        assert _WEEK in response.headers["Cache-Control"]

    def test_a_missing_pdf_404_is_not_cached(self) -> None:
        """
        The half of the bug that outlived the outage.

        Django's ``cache_control`` patches every response, so the 404 a
        vanished mount produced was stored for a week and the browser
        would not re-request the book even once the file came back.
        """
        self.paths[0].unlink()
        response = self.client.get(self._pdf_url())
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code
        assert _WEEK not in response.headers.get("Cache-Control", "")

    def test_a_missing_comic_row_404_is_not_cached(self) -> None:
        """An ACL miss or a deleted row must not be cached either."""
        missing_pk = max(c.pk for c in self.comics) + 1000
        response = self.client.get(f"/c/{missing_pk}/book.pdf")
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code
        assert _WEEK not in response.headers.get("Cache-Control", "")

    def test_an_unreadable_opds_page_404_is_not_cached(self) -> None:
        """The OPDS binary page route carried the same week-long patch."""
        with _unreadable(self.paths[0]):
            response = self.client.get(
                f"/opds/bin/c/{self.comics[0].pk}/0/page.jpg",
            )
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code
        assert _WEEK not in response.headers.get("Cache-Control", "")

    # ── The reader page ────────────────────────────────────────────────

    def test_a_readable_page_is_still_served(self) -> None:
        """Sanity: the example archive really does yield a page."""
        response = self.client.get(self._page_url())
        assert response.status_code == _HTTP_OK, response.status_code
        assert response.content

    def test_an_unreadable_page_is_not_found(self) -> None:
        """``FileNotFoundError`` was caught; its ``OSError`` siblings were not."""
        with _unreadable(self.paths[0]):
            response = self.client.get(self._page_url())
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code

    def test_the_page_error_does_not_name_the_file(self) -> None:
        """The old detail string echoed the raw ``OSError``, path and all."""
        self.paths[0].unlink()
        response = self.client.get(self._page_url())
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code
        assert str(self.paths[0]) not in response.content.decode()

    # ── The collection zip ─────────────────────────────────────────────

    def test_a_whole_collection_zips(self) -> None:
        """Sanity: both comics are in the archive."""
        response = self.client.get(self._collection_url())
        assert response.status_code == _HTTP_OK, response.status_code
        body = _body(response)
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            assert sorted(zf.namelist()) == ["c1.cbz", "c2.cbz"]
        assert "X-Codex-Skipped-Comics" not in response.headers

    def test_an_unreadable_comic_is_skipped_not_streamed_broken(self) -> None:
        """
        D2: skip and stream the rest.

        Before, the response committed a 200 and then raised partway
        through, handing the client a truncated zip under a success
        status. The skip happens before the headers so the count can
        ride along in one.
        """
        with _unreadable(self.paths[1]):
            response = self.client.get(self._collection_url())
            assert response.status_code == _HTTP_OK, response.status_code
            body = _body(response)

        assert response.headers["X-Codex-Skipped-Comics"] == "1"
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            assert zf.namelist() == ["c1.cbz"]
            assert zf.testzip() is None
        assert int(response.headers["Content-Length"]) == len(body)

    def test_a_missing_comic_is_skipped_too(self) -> None:
        """``add_path`` raises ``FileNotFoundError`` of its own accord."""
        self.paths[1].unlink()
        response = self.client.get(self._collection_url())
        assert response.status_code == _HTTP_OK, response.status_code
        body = _body(response)
        assert response.headers["X-Codex-Skipped-Comics"] == "1"
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            assert zf.namelist() == ["c1.cbz"]

    def test_a_collection_of_unreadable_comics_is_not_found(self) -> None:
        """An empty archive is not a success; nothing could be served."""
        with _unreadable(*self.paths):
            response = self.client.get(self._collection_url())
        assert response.status_code == _HTTP_NOT_FOUND, response.status_code
