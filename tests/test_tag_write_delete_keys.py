"""
Clearing a tag-editor field must actually clear it in the archive.

A merge write can only add or replace values — comicbox prunes empty patch
values on schema load — so cleared fields travel as ``delete_keys`` glom key
paths: view → ``BulkTagWriteTask`` → ``BulkWriteItem`` → comicbox's
``general.delete_keys``. Regression: empty markers (``""``/``{}``/``null``)
in the patch made every "clear field" action a silent no-op on the archive.
"""

from __future__ import annotations

import json
import shutil
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final, override
from unittest.mock import MagicMock, patch

from comicbox.box import Comicbox
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from loguru import logger

from codex.librarian.scribe.tag_writer import TagWriter
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import Comic, Imprint, Library, Publisher, Series, Volume
from codex.settings import COMICBOX_CONFIG
from codex.startup import init_admin_flags

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_TMP_DIR: Final = Path("/tmp/codex.tests.tagwritedeletekeys")  # noqa: S108
_TAG_WRITE_URL: Final = "/api/v4/admin/tag-write"
_EXAMPLE_CBZ: Final = Path(__file__).parent / "files" / "comicbox-2-example.cbz"


def _double(stub: object) -> Any:
    """Pass a test double through a concretely-typed seam."""
    return stub


def _make_comic(path: Path) -> Comic:
    library = Library.objects.create(path=str(_TMP_DIR), events=False)
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
    volume = Volume.objects.create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    return Comic.objects.create(
        library=library,
        path=path,
        issue_number=1,
        name="c",
        publisher=publisher,
        imprint=imprint,
        series=series,
        volume=volume,
        size=1,
        file_type="CBZ",
    )


def _make_writer() -> TagWriter:
    """Build a TagWriter without the threading machinery."""
    writer = TagWriter.__new__(TagWriter)
    writer.log = _double(logger)
    writer.librarian_queue = _double(MagicMock())
    writer.status_controller = _double(MagicMock())
    writer.abort_event = threading.Event()
    return writer


def _read_sub_md(path: Path) -> dict:
    with Comicbox(path) as cb:
        return dict(cb.get_internal_metadata().get("comicbox", {}))


class TagWriteViewDeleteKeysTestCase(TestCase):
    """The tag-write view forwards deleteKeys into the enqueued task."""

    @override
    def setUp(self) -> None:
        cache.clear()
        init_admin_flags()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        path = _TMP_DIR / "c.cbz"
        path.touch()
        self.comic = _make_comic(path)  # pyright: ignore[reportUninitializedInstanceVariable]
        admin = User.objects.create_user(
            username="delete_keys_admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def _post_tag_write(self, payload: dict) -> BulkTagWriteTask:
        with patch("codex.views.admin.tagwrite.LIBRARIAN_QUEUE") as queue:
            resp = self.client.post(
                _TAG_WRITE_URL,
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert resp.status_code == HTTPStatus.ACCEPTED, resp.content
            assert queue.put.called, "no tag write task was enqueued"
            return queue.put.call_args.args[0]

    def test_delete_keys_reach_the_task(self) -> None:
        """DeleteKeys (camelCase over the wire) lands on the task."""
        task = self._post_tag_write(
            {
                "collection": "publishers",
                "pks": [str(self.comic.publisher.pk)],
                "patch": json.dumps({"age_rating": "Teen"}),
                "deleteKeys": ["summary", "community_rating"],
                "mode": "update",
                "formats": ["COMIC_INFO"],
            }
        )
        assert task.delete_keys == ("summary", "community_rating")
        assert task.patch == {"age_rating": "Teen"}

    def test_clear_only_write_needs_no_patch(self) -> None:
        """A pure-clear edit sends an empty patch and only deleteKeys."""
        task = self._post_tag_write(
            {
                "collection": "publishers",
                "pks": [str(self.comic.publisher.pk)],
                "patch": json.dumps({}),
                "deleteKeys": ["summary"],
                "mode": "update",
                "formats": ["COMIC_INFO"],
            }
        )
        assert task.delete_keys == ("summary",)
        assert not task.patch

    def test_omitted_delete_keys_default_empty(self) -> None:
        task = self._post_tag_write(
            {
                "collection": "publishers",
                "pks": [str(self.comic.publisher.pk)],
                "patch": json.dumps({"age_rating": "Teen"}),
                "mode": "update",
                "formats": ["COMIC_INFO"],
            }
        )
        assert task.delete_keys == ()


class TagWriterDeleteKeysTestCase(TestCase):
    """TagWriter carries delete_keys into comicbox and the archive changes."""

    @override
    def setUp(self) -> None:
        cache.clear()
        _TMP_DIR.mkdir(exist_ok=True, parents=True)
        self.cbz_path = _TMP_DIR / "example.cbz"  # pyright: ignore[reportUninitializedInstanceVariable]
        shutil.copy(_EXAMPLE_CBZ, self.cbz_path)
        self.comic = _make_comic(self.cbz_path)  # pyright: ignore[reportUninitializedInstanceVariable]

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_build_items_passes_delete_keys(self) -> None:
        """Every built item carries the task's delete_keys."""
        writer = _make_writer()
        task = BulkTagWriteTask(
            comic_pks=frozenset({self.comic.pk}),
            patch={"age_rating": "Teen"},
            delete_keys=("summary",),
        )
        items = writer._build_items(task, {self.comic.pk: self.cbz_path})  # noqa: SLF001
        assert len(items) == 1
        assert items[0].delete_keys == frozenset({"summary"})
        assert items[0].patch == {"age_rating": "Teen"}

    def test_build_items_emits_delete_only_items(self) -> None:
        """A clear-only task (no patch at all) still writes."""
        writer = _make_writer()
        task = BulkTagWriteTask(
            comic_pks=frozenset({self.comic.pk}),
            delete_keys=("summary",),
        )
        items = writer._build_items(task, {self.comic.pk: self.cbz_path})  # noqa: SLF001
        assert len(items) == 1
        assert items[0].delete_keys == frozenset({"summary"})
        assert items[0].patch == {}

    def test_build_items_without_patch_or_delete_keys_skips(self) -> None:
        writer = _make_writer()
        task = BulkTagWriteTask(comic_pks=frozenset({self.comic.pk}))
        items = writer._build_items(task, {self.comic.pk: self.cbz_path})  # noqa: SLF001
        assert items == []

    def test_write_tags_clears_field_in_archive(self) -> None:
        """End-to-end: the cleared field vanishes from the archive on disk."""
        before = _read_sub_md(self.cbz_path)
        assert before.get("summary"), "test archive must start with a summary"

        writer = _make_writer()
        task = BulkTagWriteTask(
            comic_pks=frozenset({self.comic.pk}),
            patch={"age_rating": "Teen"},
            delete_keys=("summary",),
            mode="update",
            formats=("COMIC_INFO",),
        )
        writer.write_tags(task)

        after = _read_sub_md(self.cbz_path)
        assert "summary" not in after
        assert str(after.get("age_rating")) == "Teen"

    def test_write_base_config_never_carries_read_delete_keys(self) -> None:
        """
        The write base config must not inherit codex's parse-skip keys.

        Comicbox unions a write's delete_keys with the base config's, and
        the read-side COMICBOX_CONFIG skips every schema field codex does
        not consume. Using it as a write base would strip all of them from
        the user's archive.
        """
        assert COMICBOX_CONFIG.general.delete_keys, (
            "read config should carry parse-skip keys"
        )
        for delete_original in (False, True):
            task = BulkTagWriteTask(
                comic_pks=frozenset({self.comic.pk}), delete_original=delete_original
            )
            config = TagWriter._build_base_config(task)  # noqa: SLF001
            if config is not None:
                assert not config.general.delete_keys
