"""Shared fixtures for the shelves tests."""

import json
import shutil
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import (
    Comic,
    Imprint,
    Library,
    Publisher,
    Series,
    Shelf,
    ShelfItem,
    Volume,
)
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
HTTP_OK: Final = 200
HTTP_CREATED: Final = 201
HTTP_NO_CONTENT: Final = 204
HTTP_BAD_REQUEST: Final = 400
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404

LIST_URL: Final = "/api/v4/shelves/"
SETTINGS_URL: Final = "/api/v4/browse/publishers/settings"
SAVED_URL: Final = "/api/v4/browse/publishers/saved-settings"
TMP_DIR: Final = tmp_dir("codex.tests.shelves")
COLLECTIONS: Final = frozenset(
    {"publishers", "imprints", "series", "volumes", "folders", "arcs", "comics"}
)


def detail_url(shelf_pk: int) -> str:
    """Return the url of one shelf."""
    return f"{LIST_URL}{shelf_pk}"


def items_url(shelf_pk: int) -> str:
    """Return the url of one shelf's items."""
    return f"{LIST_URL}{shelf_pk}/items"


def v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def post_json(client: Client, method: str, url: str, payload: dict):
    """Send ``payload`` as JSON with the given client method."""
    return getattr(client, method)(
        url, data=json.dumps(payload), content_type="application/json"
    )


def make_chain(library: Library, suffix: str):
    """Create one publisher → imprint → series → volume → comic chain."""
    publisher = Publisher.objects.create(name=f"P{suffix}")
    imprint = Imprint.objects.create(name=f"I{suffix}", publisher=publisher)
    series = Series.objects.create(
        name=f"S{suffix}", publisher=publisher, imprint=imprint
    )
    volume = Volume.objects.create(
        name=suffix, publisher=publisher, imprint=imprint, series=series
    )
    path = TMP_DIR / f"c{suffix}.cbz"
    path.touch()
    comic = Comic.objects.create(
        library=library,
        path=path,
        issue_number=int(suffix),
        name=f"C{suffix}",
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=1,
    )
    return publisher, imprint, series, volume, comic


class ShelfTestCase(TestCase):
    """Shared fixture: a logged-in user and two parallel comic chains."""

    @override
    def setUp(self) -> None:
        # Browser views go through cachalot. Clearing the cache between
        # tests keeps an earlier test's cached listing from masking this
        # one's expected result.
        cache.clear()
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)

        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="shelver", password=TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.library = Library.objects.create(path=str(TMP_DIR))  # pyright: ignore[reportUninitializedInstanceVariable]
        self.p1, self.i1, self.s1, self.v1, self.c1 = make_chain(self.library, "1")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.p2, self.i2, self.s2, self.v2, self.c2 = make_chain(self.library, "2")  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _shelf(self, name: str = "Want to Read", user: User | None = None) -> Shelf:
        return Shelf.objects.create(user=user or self.user, name=name)

    @staticmethod
    def _target_ids(shelf: Shelf) -> list[int]:
        return list(
            ShelfItem.objects.filter(shelf=shelf)
            .order_by("pk")
            .values_list("target_id", flat=True)
        )

    @staticmethod
    def _put(shelf: Shelf, collection: str, target_id: int) -> None:
        ShelfItem.objects.create(
            shelf=shelf, collection=collection, target_id=target_id
        )
