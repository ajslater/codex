"""
Tests for the 0056 one-time re-read migration.

Comicbox 5 changes what an unchanged file means, and codex re-reads a
comic only when its file changed, so the upgrade has to ask for the
re-read explicitly. It asks by clearing the two things the skip is
decided on, which is also what makes it resumable: a comic gets its stat
back only once it has been imported.
"""

import importlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import override

from django.apps import apps
from django.test import TestCase

from codex.librarian.scribe.importer.read.extract import ExtractMetadataImporter
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume

_MIGRATION = importlib.import_module("codex.migrations.0056_comicbox_5_reread")
_request_reread = _MIGRATION._request_reread  # noqa: SLF001

TMP_DIR = Path("/tmp/codex.tests.comicbox-5-reread")  # noqa: S108
_A_STAT = (33204, 1, 16777232, 1, 501, 20, 4096, 1750000000, 1750000000.0, 1750000000)
_AN_MTIME = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


class ComicboxFiveRereadMigrationTestCase(TestCase):
    """The migration asks the poller and the importer for every comic."""

    @override
    def setUp(self) -> None:
        """Seed two comics that look freshly imported."""
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.library = Library.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            path=str(TMP_DIR), last_poll=datetime(2026, 8, 1, tzinfo=UTC)
        )
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        for name in ("one", "two"):
            path = TMP_DIR / f"{name}.cbz"
            path.touch()
            Comic.objects.create(
                library=self.library,
                path=path,
                issue_number=1,
                name=name,
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                size=1,
                stat=list(_A_STAT),
                metadata_mtime=_AN_MTIME,
                metadata_imported_at=_AN_MTIME,
            )

    @override
    def tearDown(self) -> None:
        """Remove the comic stub files."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        super().tearDown()

    def _run(self) -> None:
        _request_reread(apps, None)

    def test_every_comic_is_asked_for(self) -> None:
        """Both of the skip signals are cleared, for every row."""
        self._run()

        for comic in Comic.objects.all():
            assert comic.stat is None
            assert comic.metadata_mtime is None

    def test_the_import_marker_survives(self) -> None:
        """
        A comic already imported must not read as never imported.

        The marker drives the "not imported" hint; clearing it would
        blank that hint library-wide for the length of the re-read.
        """
        self._run()

        for comic in Comic.objects.all():
            assert comic.metadata_imported_at == _AN_MTIME

    def test_the_first_pass_comes_forward(self) -> None:
        """A null last_poll polls on the next loop, not after poll_every."""
        self._run()

        self.library.refresh_from_db()
        assert self.library.last_poll is None

    def test_manual_polling_is_left_alone(self) -> None:
        """A library its admin polls by hand keeps deciding when."""
        self.library.poll = False
        self.library.save()

        self._run()

        self.library.refresh_from_db()
        assert self.library.poll is False

    def test_a_cleared_comic_survives_the_import_prefilter(self) -> None:
        """
        The prefilter is what the cleared fields have to get past.

        It skips a comic on a matching stored stat or an unadvanced
        metadata mtime. With neither recorded there is nothing to match,
        so the comic is read again — which is the whole point.
        """
        self._run()
        paths = [str(comic.path) for comic in Comic.objects.all()]

        survivors, skipped = ExtractMetadataImporter._filesystem_mtime_prefilter(  # noqa: SLF001
            paths,
            MappingProxyType({}),  # no recorded metadata mtimes
            MappingProxyType({}),  # no recorded stats
        )

        assert set(survivors) == set(paths)
        assert not skipped

    def test_is_idempotent(self) -> None:
        """Running it twice asks for the same thing."""
        self._run()
        self._run()

        assert not Comic.objects.exclude(stat=None).exists()
