"""
End-to-end breadcrumb resolution.

Breadcrumbs walk the FK parent hierarchy and emit one crumb per level.
After the collection value-flip, ``self.kwargs["group"]`` is a collection
value (``"volumes"``), so the parent-chain map and the root crumb must be
keyed/built with ``Group`` members — otherwise the chain lookup misses and
nested-group breadcrumbs collapse to just ``[root, current]``. These pin the
full chain + the collection wire shape.
"""

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_TMP_DIR: Final = Path("/tmp/codex.tests.breadcrumbs")  # noqa: S108


def _v4(response):
    body = response.json()
    return body["data"] if isinstance(body, dict) and "data" in body else body


class BreadcrumbsTestCase(TestCase):
    """Browser breadcrumb resolution across the group hierarchy."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        library = Library.objects.create(path=str(_TMP_DIR))
        self.publisher = Publisher.objects.create(name="Pub")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.imprint = Imprint.objects.create(name="Imp", publisher=self.publisher)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Ser", imprint=self.imprint, publisher=self.publisher
        )
        self.volume = Volume.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="2024",
            series=self.series,
            imprint=self.imprint,
            publisher=self.publisher,
        )
        path = _TMP_DIR / "c1.cbz"
        path.touch()
        Comic.objects.create(
            library=library,
            path=path,
            issue_number=1,
            name="C1",
            publisher=self.publisher,
            imprint=self.imprint,
            series=self.series,
            volume=self.volume,
            size=42,
            year=2024,
            page_count=20,
        )
        self.user = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="breadcrumbs_test", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.user)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _show_full_hierarchy(self) -> None:
        """
        Enable every browse group with the shallowest top group.

        ``top_group="publishers"`` keeps publishers/imprints/series/volumes all
        in the valid nav set, so drilling down to a volume produces the full
        ancestor chain. (A deeper top group would correctly *prune* the levels
        above it — root would list volumes directly.)
        """
        response = self.client.patch(
            "/api/v4/browse/publishers/settings",
            data=(
                '{"topGroup": "publishers", "show": {"publishers": true,'
                ' "imprints": true, "series": true, "volumes": true}}'
            ),
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK, response.content

    def _breadcrumbs(self, url: str) -> list[dict]:
        response = self.client.get(url)
        assert response.status_code == _HTTP_OK, response.content
        return _v4(response)["breadcrumbs"]

    def test_root_breadcrumbs_is_single_crumb(self) -> None:
        """Browsing the root publishers list yields just the root crumb."""
        crumbs = self._breadcrumbs("/api/v4/browse/publishers?page=1")
        assert len(crumbs) == 1
        assert crumbs[0]["collection"] == "publishers"
        assert crumbs[0]["parentIds"] == []
        # The legacy wire field is collection-valued now, not char "r".
        assert crumbs[0]["group"] == "root"

    def test_nested_volume_walks_the_full_parent_chain(self) -> None:
        """A volume's breadcrumbs include every ancestor, not just root+self."""
        self._show_full_hierarchy()
        crumbs = self._breadcrumbs(f"/api/v4/browse/volumes/{self.volume.pk}?page=1")
        # root → publisher → imprint → series → volume. Pre-fix this
        # collapsed to [root, volume] because the char-keyed parent-chain
        # map missed the collection-valued group lookup.
        shape = [(c["collection"], c["parentIds"]) for c in crumbs]
        assert shape == [
            ("publishers", []),
            ("publishers", [self.publisher.pk]),
            ("imprints", [self.imprint.pk]),
            ("series", [self.series.pk]),
            ("volumes", [self.volume.pk]),
        ]
        # The legacy ``group`` field is collection-valued across every crumb.
        assert [c["group"] for c in crumbs] == [
            "root",
            "publishers",
            "imprints",
            "series",
            "volumes",
        ]
