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
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Folder, Imprint, Library, Publisher, Series, Volume
from codex.models.named import StoryArc, StoryArcNumber
from codex.models.settings import SettingsReader
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.reader")  # noqa: S108


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
