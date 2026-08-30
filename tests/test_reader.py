"""
End-to-end reader vocabulary: arc-nav + settings-scope speak collection names.

The reader was flipped off single-char codes onto the collection vocabulary
(``series``/``volumes``/``folders``/``arcs`` for arcs;
``global``/``comics``/``series``/… for settings scopes). These pin the wire:
the ``arcs`` map + selected ``arc.collection`` are collection-keyed, the
settings-scope GET/PATCH round-trip on collection scope names, and the
``p/i/v→series`` collapse + ``folders``/``arcs`` keys resolve. No reader tests
existed before, which is why the earlier browser flip silently broke the
reader's series/volume arcs (``show.get("s")`` against a collection-keyed show).
"""

import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Final, override
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models.functions.datetime import Now
from django.test import Client, TestCase

from codex.librarian.scribe.timestamp_update import TimestampUpdater
from codex.models import Comic, Folder, Imprint, Library, Publisher, Series, Volume
from codex.models.named import Reprint, StoryArc, StoryArcNumber
from codex.models.settings import SettingsReader
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.reader")  # noqa: S108
_ALT_TMP_DIR: Final = Path("/tmp/codex.tests.reader_alt_series")  # noqa: S108
# The alternate series fixture holds three comics.
_ALT_SERIES_LEN: Final = 3


def _v4(response):
    body = response.json()
    return body["data"] if isinstance(body, dict) and "data" in body else body


class ReaderVocabularyTestCase(TestCase):
    """The reader's arc + scope vocabularies are collection-valued."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=imprint, publisher=publisher
        )
        volume = Volume.objects.create(
            name="2024", series=self.series, imprint=imprint, publisher=publisher
        )
        folder_path = _TMP_DIR / "f"
        folder_path.mkdir(exist_ok=True)
        folder = Folder.objects.create(library=library, path=str(folder_path))
        path = _TMP_DIR / "c1.cbz"
        path.touch()
        self.comic = Comic.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=library,
            path=path,
            issue_number=1,
            name="C1",
            publisher=publisher,
            imprint=imprint,
            series=self.series,
            volume=volume,
            parent_folder=folder,
            size=42,
            year=2024,
            page_count=20,
        )
        arc = StoryArc.objects.create(name="The Big One")
        san = StoryArcNumber.objects.create(story_arc=arc, number=1)
        self.comic.story_arc_numbers.add(san)
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="reader_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)
        # Enable series + volume groups so both arcs surface (default hides them).
        response = self.client.patch(
            "/api/v4/browse/publishers/settings",
            data=(
                '{"show": {"publishers": true, "imprints": true,'
                ' "series": true, "volumes": true}}'
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_reader_arcs_are_collection_keyed(self) -> None:
        """The arcs map + selected arc.collection use collection names, not chars."""
        response = self.client.get(f"/api/v4/reader/comics/{self.comic.pk}")
        assert response.status_code == _HTTP_OK, response.content
        data = _v4(response)
        # Every arc the comic belongs to is keyed by its collection name.
        # Pre-fix the series/volume arcs were dropped (show.get("s") missed)
        # and the folder arc was keyed by the char "f".
        assert set(data["arcs"]) == {"series", "volumes", "folders", "arcs"}
        assert not ({"s", "v", "f"} & set(data["arcs"]))
        # The selected arc group is a valid collection arc group.
        assert data["arc"]["collection"] in {"series", "volumes", "folders", "arcs"}

    def test_reader_settings_scopes_are_collection_keyed(self) -> None:
        """GET ?scopes=global,series,comics returns collection-keyed scopes."""
        url = (
            f"/api/v4/comics/{self.comic.pk}/reader-settings"
            "?scopes=global,series,comics"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        scopes = _v4(response)["scopes"]
        assert {"global", "series", "comics"} <= set(scopes)
        assert not ({"g", "s", "c"} & set(scopes))

    def test_volume_scope_collapses_to_series(self) -> None:
        """The ``volumes`` arc scope canonicalises to ``series`` in the response."""
        url = (
            f"/api/v4/comics/{self.comic.pk}/reader-settings"
            "?scopes=global,volumes,comics"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        scopes = _v4(response)["scopes"]
        # Requested "volumes" comes back under the canonical "series" key.
        assert "series" in scopes
        assert "volumes" not in scopes

    def test_scoped_patch_persists_on_series_row(self) -> None:
        """PATCH scope=series writes a SettingsReader row keyed by series_id."""
        url = f"/api/v4/comics/{self.comic.pk}/reader-settings"
        response = self.client.patch(
            url,
            data=json.dumps(
                {"scope": "series", "scopePk": self.series.pk, "fitTo": "H"}
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content
        row = SettingsReader.objects.filter(series_id=self.series.pk).first()
        assert row is not None
        assert row.fit_to == "H"


class ReaderAlternateSeriesArcTestCase(TestCase):
    """Reading an alternate series (ComicInfo AlternateSeries) as a reading order."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _ALT_TMP_DIR.mkdir(parents=True, exist_ok=True)
        self.library = Library.objects.create(path=str(_ALT_TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Imp", publisher=self.publisher
        )
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=self.imprint, publisher=self.publisher
        )
        self.volume = Volume.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="2024",
            series=self.series,
            imprint=self.imprint,
            publisher=self.publisher,
        )
        folder_path = _ALT_TMP_DIR / "f"
        folder_path.mkdir(exist_ok=True)
        self.folder = Folder.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            library=self.library, path=str(folder_path)
        )
        # Regular issue order is deliberately the reverse of the alternate
        # order, so a reading order that silently fell back to the series
        # would produce the opposite sequence.
        self.c_first = self._create_comic("C1", 30, "2")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.c_middle = self._create_comic("C2", 20, "3")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.c_last = self._create_comic("C3", 10, "10")  # pyright: ignore[reportUninitializedInstanceVariable]
        user = User.objects.create_user(
            username="reader_alt_series_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_ALT_TMP_DIR, ignore_errors=True)

    def _create_comic(self, name: str, issue_number: int, alt_issue: str) -> Comic:
        path = _ALT_TMP_DIR / f"{name.lower()}.cbz"
        path.touch()
        comic = Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=issue_number,
            name=name,
            publisher=self.publisher,
            imprint=self.imprint,
            series=self.series,
            volume=self.volume,
            parent_folder=self.folder,
            size=42 + issue_number,
            year=2024,
            page_count=20,
        )
        comic.reprints.add(
            Reprint.objects.create(series_name="Crossover", issue=alt_issue)
        )
        return comic

    def _reader(self, comic: Comic, arc: dict | None = None) -> dict:
        url = f"/api/v4/reader/comics/{comic.pk}"
        if arc:
            url += f"?arc={json.dumps(arc)}"
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)

    def _alt_arc(self, data: dict) -> tuple[str, dict]:
        """Return the single alternate-series arc's (ids, info)."""
        arcs = data["arcs"]["reprints"]
        assert len(arcs) == 1, arcs
        ids, info = next(iter(arcs.items()))
        return ids, info

    def test_alternate_series_is_offered_as_an_arc(self) -> None:
        """The reader lists the alternate series among its reading orders."""
        data = self._reader(self.c_first)
        assert "reprints" in data["arcs"], data["arcs"]
        _, info = self._alt_arc(data)
        assert info["name"] == "Crossover", info
        assert info["mtime"], info

    def test_arc_ids_cover_the_whole_group(self) -> None:
        """The arc handle is every Reprint row in the series, not just this comic's."""
        # Each issue of an alternate series is its own Reprint row, so a
        # per-comic handle would change from book to book.
        ids, _ = self._alt_arc(self._reader(self.c_first))
        expected = sorted(
            Reprint.objects.filter(series_name="Crossover").values_list("pk", flat=True)
        )
        assert sorted(int(pk) for pk in str(ids).split(",")) == expected

    def test_books_follow_the_alternate_number(self) -> None:
        """prev/next walk 2 -> 3 -> 10, not the regular issue order."""
        ids, _ = self._alt_arc(self._reader(self.c_first))
        arc = {"collection": "reprints", "ids": [int(pk) for pk in str(ids).split(",")]}

        data = self._reader(self.c_middle, arc)
        assert data["arc"]["collection"] == "reprints", data["arc"]
        assert data["books"]["prev"]["pk"] == self.c_first.pk, data["books"]
        assert data["books"]["next"]["pk"] == self.c_last.pk, data["books"]

    def test_arc_selection_survives_the_next_book(self) -> None:
        """The same ids keep selecting the alternate series on another comic."""
        ids, _ = self._alt_arc(self._reader(self.c_first))
        arc = {"collection": "reprints", "ids": [int(pk) for pk in str(ids).split(",")]}

        data = self._reader(self.c_last, arc)
        assert data["arc"]["collection"] == "reprints", data["arc"]
        # C3 carries alternate number 10, the last of the three.
        assert data["arc"]["index"] == _ALT_SERIES_LEN, data["arc"]
        assert data["arc"]["count"] == _ALT_SERIES_LEN, data["arc"]

    def test_absent_alternate_series_falls_back(self) -> None:
        """Requesting an alternate series a comic isn't in still reads."""
        path = _ALT_TMP_DIR / "lonely.cbz"
        path.touch()
        lonely = Comic.objects.create(
            library=self.library,
            path=path,
            issue_number=99,
            name="Lonely",
            publisher=self.publisher,
            imprint=self.imprint,
            series=self.series,
            volume=self.volume,
            parent_folder=self.folder,
            size=1,
            year=2024,
            page_count=1,
        )
        data = self._reader(lonely, {"collection": "reprints", "ids": [1, 2, 3]})
        assert data["arc"]["collection"] != "reprints", data["arc"]

    def test_reader_settings_ignore_the_reprint_scope(self) -> None:
        """``reprints`` has no settings scope of its own and doesn't error."""
        url = (
            f"/api/v4/comics/{self.c_first.pk}/reader-settings"
            "?scopes=global,reprints,comics"
        )
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        scopes = _v4(response)["scopes"]
        assert "reprints" not in scopes, scopes
        assert "global" in scopes, scopes

    def test_mtime_probe_accepts_the_alternate_series_arc(self) -> None:
        """The reader probes every arc it offers, alternate series included."""
        ids, _ = self._alt_arc(self._reader(self.c_first))
        collections = json.dumps([{"collection": "reprints", "pks": str(ids)}])
        response = self.client.get(f"/api/v4/mtime?collections={collections}")
        assert response.status_code == _HTTP_OK, response.content
        assert _v4(response)["maxMtime"], response.content

    def test_timestamp_updater_restamps_reprints(self) -> None:
        """A changed comic advances its alternate series' mtime."""
        # Without this the reader's mtime probe never notices a re-import
        # and an open reader keeps showing stale books.
        reprint = Reprint.objects.get(comic=self.c_first)
        before = reprint.updated_at
        start_time = before - timedelta(seconds=5)
        Comic.objects.filter(pk=self.c_first.pk).update(updated_at=Now())

        updater = TimestampUpdater(Mock(), Mock(), Mock())
        updater.update_library_collections(self.library, start_time, {})

        reprint.refresh_from_db()
        assert reprint.updated_at > before
