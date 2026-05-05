"""
Regression tests for the metadata view's ``*_list`` projection.

The metadata response embeds ``publisherList`` / ``imprintList`` /
``seriesList`` / ``volumeList`` / ``storyArcList`` for the chips in the
metadata dialog. ``GroupSerializer`` requires each row to expose
``ids`` (and ``number_to`` for Volume); without ``ids`` the frontend
``toVuetifyItem`` collapses every entry into a single "None" chip and
single-id rows lose their click target. See PR #725.

These tests pin the contract end-to-end through the HTTP layer so that
both projection sites — ``_query_groups`` (parent groups, populated
when the current group is below them) and ``_highlight_current_group``
(current group, populated for top-level group views) — keep emitting
``ids`` for every row.
"""

import shutil
from pathlib import Path
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase

from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.models.named import StoryArc
from codex.startup import init_admin_flags
from codex.views.browser.metadata.group_list import group_list_field_name

TMP_DIR = Path("/tmp/codex.tests.metadata_group_list")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
_EXPECTED_PUBLISHER_ROWS: Final = 2


class MetadataGroupListTestCase(TestCase):
    """Pin the ``GroupSerializer`` shape on every metadata ``*_list`` field."""

    @override
    def setUp(self) -> None:
        """Seed two publishers (case-different names) sharing one comic each."""
        # Migrations don't seed every AdminFlag the request pipeline reads
        # (notably ``NU`` for ``IsAuthenticatedOrEnabledNonUsers``); rely
        # on the same idempotent seeder ``codex.run`` calls at startup.
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        library = Library.objects.create(path=str(TMP_DIR))
        # Two publishers with case-different names — the original bug
        # reproducer. Their ``sort_name`` collides ("boom! studios"), so
        # ``add_group_by`` aggregates both pks onto a single metadata
        # row, exercising the multi-id path through ``obj.ids``.
        self.pub_a = Publisher.objects.create(name="Boom! Studios")  # pyright: ignore[reportUninitializedInstanceVariable]
        self.pub_b = Publisher.objects.create(name="BOOM! Studios")  # pyright: ignore[reportUninitializedInstanceVariable]
        imprint_a = Imprint.objects.create(name="Imp A", publisher=self.pub_a)
        imprint_b = Imprint.objects.create(name="Imp B", publisher=self.pub_b)
        series_a = Series.objects.create(
            name="Ser A", imprint=imprint_a, publisher=self.pub_a
        )
        series_b = Series.objects.create(
            name="Ser B", imprint=imprint_b, publisher=self.pub_b
        )
        volume_a = Volume.objects.create(
            name="2024", series=series_a, imprint=imprint_a, publisher=self.pub_a
        )
        volume_b = Volume.objects.create(
            name="2025", series=series_b, imprint=imprint_b, publisher=self.pub_b
        )

        def _comic(suffix: str, pub, imp, ser, vol) -> Comic:
            path = TMP_DIR / f"{suffix}.cbz"
            path.touch()
            return Comic.objects.create(
                library=library,
                path=path,
                issue_number=1,
                name=suffix,
                publisher=pub,
                imprint=imp,
                series=ser,
                volume=vol,
                size=1,
            )

        self.comic_a = _comic("a", self.pub_a, imprint_a, series_a, volume_a)  # pyright: ignore[reportUninitializedInstanceVariable]
        self.comic_b = _comic("b", self.pub_b, imprint_b, series_b, volume_b)  # pyright: ignore[reportUninitializedInstanceVariable]

        user = User.objects.create_user(
            username="metadata_grouplist", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.force_login(user)

    @override
    def tearDown(self) -> None:
        """Remove the temp comic tree."""
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    def _get_metadata(self, group: str, pks: list[int]) -> dict:
        joined = ",".join(str(p) for p in pks)
        url = f"/api/v3/{group}/{joined}/metadata"
        response = self.client.get(url)
        if response.status_code != _HTTP_OK:
            reason = f"GET {url} returned {response.status_code}: {response.content!r}"
            raise AssertionError(reason)
        return response.json()

    # --- current-group path (``_highlight_current_group``) ---

    def test_publisher_metadata_multi_id_includes_ids(self) -> None:
        """Multi-pk publisher view emits one ``publisherList`` row per name, each with ``ids``."""
        data = self._get_metadata("p", [self.pub_a.pk, self.pub_b.pk])
        publisher_list = data.get("publisherList") or []
        # Two publishers with different names ⇒ two rows.
        assert len(publisher_list) == _EXPECTED_PUBLISHER_ROWS, publisher_list
        names = {row["name"] for row in publisher_list}
        assert names == {"Boom! Studios", "BOOM! Studios"}, names
        # Every row carries non-empty ``ids`` — the bug PR #725 fixed.
        for row in publisher_list:
            assert row.get("ids"), row
            assert all(isinstance(pk, int) for pk in row["ids"]), row

    def test_publisher_metadata_single_id_includes_ids(self) -> None:
        """Single-pk publisher view also includes ``ids`` (single-chip click target)."""
        data = self._get_metadata("p", [self.pub_a.pk])
        publisher_list = data.get("publisherList") or []
        assert len(publisher_list) == 1, publisher_list
        row = publisher_list[0]
        assert row["name"] == "Boom! Studios"
        assert row["ids"] == [self.pub_a.pk]

    def test_volume_metadata_includes_number_to(self) -> None:
        """Volume current-group view exposes ``number_to`` for ``formattedVolumeName``."""
        volume_pk = Volume.objects.get(name="2024").pk
        data = self._get_metadata("v", [volume_pk])
        volume_list = data.get("volumeList") or []
        assert len(volume_list) == 1, volume_list
        row = volume_list[0]
        # ``number_to`` is camelCased by the serializer.
        assert "numberTo" in row, row
        assert row["ids"] == [volume_pk]

    # --- parent-group path (``_query_groups``) ---

    def test_series_metadata_includes_publisher_parent_with_ids(self) -> None:
        """Series view's parent ``publisherList`` is populated with ``ids``."""
        series = Series.objects.get(name="Ser A")
        data = self._get_metadata("s", [series.pk])
        publisher_list = data.get("publisherList") or []
        assert len(publisher_list) == 1, publisher_list
        row = publisher_list[0]
        assert row["name"] == "Boom! Studios"
        assert row["ids"] == [self.pub_a.pk]


class GroupListFieldNameTestCase(TestCase):
    """Pin the ``model -> *_list`` attribute mapping the serializer reads."""

    def test_publisher_field_name(self) -> None:
        """Publisher → ``publisher_list``."""
        assert group_list_field_name(Publisher) == "publisher_list"

    def test_imprint_field_name(self) -> None:
        """Imprint → ``imprint_list``."""
        assert group_list_field_name(Imprint) == "imprint_list"

    def test_series_field_name(self) -> None:
        """Series → ``series_list``."""
        assert group_list_field_name(Series) == "series_list"

    def test_volume_field_name(self) -> None:
        """Volume → ``volume_list``."""
        assert group_list_field_name(Volume) == "volume_list"

    def test_story_arc_field_name_is_overridden(self) -> None:
        """
        StoryArc → ``story_arc_list`` (not the default ``storyarc_list``).

        Without the override the metadata response silently dropped
        ``storyArcList`` because the serializer only reads
        ``story_arc_list``.
        """
        assert group_list_field_name(StoryArc) == "story_arc_list"
