"""
GET /metadata must never write to the database.

``_copy_m2m_intersections`` used to call ``ManyRelatedManager.set(qs,
clear=True)`` for every real m2m field on the Comic path — DELETE+INSERT
across the through tables on a GET. On a multi-comic selection that
permanently rewrote the first comic's tags to the selection's
*intersection* (e.g. 339 characters silently became 43). The fix serves
the intersection through the instance's prefetch cache instead.

These tests pin: zero m2m writes on GET, tags untouched afterwards, and
the multi-select response still showing exactly the intersection.
"""

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from codex.models import (
    Character,
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Tag,
    Volume,
)
from codex.startup import init_admin_flags

TMP_DIR = Path("/tmp/codex.tests.metadata_get_no_writes")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_WRITE_VERBS: Final = ("INSERT", "UPDATE", "DELETE")


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _m2m_writes(captured_queries) -> list[str]:
    """Return captured statements that write to comic m2m through tables."""
    return [
        q["sql"]
        for q in captured_queries
        if q["sql"].split(" ", 1)[0].upper() in _WRITE_VERBS
        and "codex_comic_" in q["sql"]
    ]


class MetadataGetNoWritesTestCase(TestCase):
    """GET /metadata is read-only and computes intersections correctly."""

    @override
    def setUp(self) -> None:
        """Seed two comics with overlapping m2m tag sets."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        publisher = Publisher.objects.create(name="Pub")
        imprint = Imprint.objects.create(name="Imp", publisher=publisher)
        series = Series.objects.create(name="Ser", imprint=imprint, publisher=publisher)
        volume = Volume.objects.create(
            name="2024", series=series, imprint=imprint, publisher=publisher
        )
        comics = []
        for n in (1, 2):
            path = TMP_DIR / f"c{n}.cbz"
            path.touch()
            comics.append(
                Comic.objects.create(
                    library=library,
                    path=path,
                    issue_number=n,
                    name=f"C{n}",
                    publisher=publisher,
                    imprint=imprint,
                    series=series,
                    volume=volume,
                    size=42,
                )
            )
        self.comic1, self.comic2 = comics  # pyright: ignore[reportUninitializedInstanceVariable]
        char_a = Character.objects.create(name="Alpha")
        char_b = Character.objects.create(name="Beta")
        char_c = Character.objects.create(name="Gamma")
        self.comic1.characters.set([char_a, char_b])
        self.comic2.characters.set([char_b, char_c])
        self.shared_char = char_b  # pyright: ignore[reportUninitializedInstanceVariable]
        tag = Tag.objects.create(name="OnlyOnOne")
        self.comic1.tags.set([tag])

        user = User.objects.create_user(
            username="md_reader", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _get_metadata(self, pks: str):
        url = f"/api/v4/browse/comics/{pks}/metadata"
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        writes = _m2m_writes(ctx.captured_queries)
        assert not writes, f"GET {url} wrote through tables: {writes}"
        return _v4(response)

    def test_single_comic_metadata_is_read_only(self) -> None:
        """Single-comic GET issues no m2m writes and shows the comic's tags."""
        data = self._get_metadata(str(self.comic1.pk))
        names = sorted(c["name"] for c in data["characters"])
        assert names == ["Alpha", "Beta"], names

    def test_multi_select_shows_intersection_without_corrupting(self) -> None:
        """Multi-select shows A∩B and leaves both comics' tags untouched."""
        before1 = sorted(self.comic1.characters.values_list("pk", flat=True))
        before_tags = sorted(self.comic1.tags.values_list("pk", flat=True))

        pks = f"{self.comic1.pk},{self.comic2.pk}"
        data = self._get_metadata(pks)
        isect = sorted(c["pk"] for c in data["characters"])
        assert isect == [self.shared_char.pk], isect
        # The pre-fix manager.set() rewrote comic1's tag sets to the
        # intersection (and cleared tags entirely).
        after1 = sorted(self.comic1.characters.values_list("pk", flat=True))
        after_tags = sorted(self.comic1.tags.values_list("pk", flat=True))
        assert after1 == before1, (before1, after1)
        assert after_tags == before_tags, (before_tags, after_tags)
