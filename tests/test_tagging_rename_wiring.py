"""
Wiring tests for the comicbox rename toggle.

Confirms ``rename`` threads through the manual tag-write view (request value or
admin default), the preflight filename preview, the tag-by-id online path, and
deferred-prompt serialization.
"""

from __future__ import annotations

import shutil
from http import HTTPStatus
from pathlib import Path
from typing import Any, ClassVar, Final, Self, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import Client, SimpleTestCase, TestCase
from loguru import logger

from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.tasks import OnlineTagByIdTask
from codex.librarian.scribe.tasks import BulkTagWriteTask
from codex.models import (
    Comic,
    ComicboxTaggingDefaults,
    Imprint,
    Library,
    Publisher,
    Series,
    Volume,
)
from codex.views.admin.tagwrite import AdminTagWritePreflightView, AdminTagWriteView

_TMP_DIR: Final = Path("/tmp/codex.tests.tagrenamewiring")  # noqa: S108
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PK: Final = 7
_TAG_WRITE_URL: Final = "/api/v4/admin/tag-write"
_PREFLIGHT_URL: Final = "/api/v4/admin/tag-write/preflight"
_QUEUE_TARGET: Final = "codex.views.admin.tagwrite.LIBRARIAN_QUEUE"
_VIEW_COMICBOX_TARGET: Final = "codex.views.admin.tagwrite.Comicbox"
_FETCH_TARGET: Final = (
    "codex.librarian.onlinetag.session_manager.fetch_tags_by_explicit_id"
)
_PREVIEW_NAME: Final = "Series v01 #001.cbz"


def _double(stub: object) -> Any:
    """Pass a test double through a concretely-typed seam."""
    return stub


class _FakeQueue:
    """Collects everything put on it for assertions."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


class _PreviewComicbox:
    """Minimal Comicbox stand-in for the preflight filename preview."""

    def __init__(self, path, **_kwargs) -> None:
        self._path = Path(path)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def to_string(self, _fmt) -> str:
        return _PREVIEW_NAME


def _make_comic() -> Comic:
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    library = Library.objects.create(path=str(_TMP_DIR))
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
    volume = Volume.objects.create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    path = _TMP_DIR / "c.cbz"
    path.write_text("comic")
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


def _make_comics(count: int) -> list[Comic]:
    """Create ``count`` comics sharing one library (unique on-disk names)."""
    _TMP_DIR.mkdir(exist_ok=True, parents=True)
    library = Library.objects.create(path=str(_TMP_DIR))
    publisher = Publisher.objects.create(name="P")
    imprint = Imprint.objects.create(name="I", publisher=publisher)
    series = Series.objects.create(name="S", publisher=publisher, imprint=imprint)
    volume = Volume.objects.create(
        name="1", publisher=publisher, imprint=imprint, series=series
    )
    comics = []
    for i in range(count):
        path = _TMP_DIR / f"c{i}.cbz"
        path.write_text("comic")
        comics.append(
            Comic.objects.create(
                library=library,
                path=path,
                issue_number=i + 1,
                name=f"c{i}",
                publisher=publisher,
                imprint=imprint,
                series=series,
                volume=volume,
                size=1,
                file_type="CBZ",
            )
        )
    return comics


def _make_admin() -> User:
    return User.objects.create_user(
        username="rename_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class TagWriteRenameViewTests(TestCase):
    """The tag-write view resolves rename from the request or admin default."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        self.client = Client()
        self.client.force_login(_make_admin())

    def _post(self, body: dict[str, Any]):
        return self.client.post(
            _TAG_WRITE_URL, data=body, content_type="application/json"
        )

    def test_rename_defaults_to_admin_setting(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"rename_files": True}
        )
        with (
            patch.object(
                AdminTagWriteView, "resolve_comic_pks", return_value=frozenset({_PK})
            ),
            patch(_QUEUE_TARGET) as mocked_queue,
        ):
            response = self._post(
                {"collection": "comics", "pks": [str(_PK)], "patch": "{}"}
            )
        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, BulkTagWriteTask)
        assert task.rename is True

    def test_request_overrides_default(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"rename_files": True}
        )
        with (
            patch.object(
                AdminTagWriteView, "resolve_comic_pks", return_value=frozenset({_PK})
            ),
            patch(_QUEUE_TARGET) as mocked_queue,
        ):
            response = self._post(
                {
                    "collection": "comics",
                    "pks": [str(_PK)],
                    "patch": "{}",
                    "rename": False,
                }
            )
        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert task.rename is False


class PreflightFilenamePreviewTests(TestCase):
    """Preflight returns a comicbox-scheme filename preview and rename default."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        self.client = Client()
        self.client.force_login(_make_admin())

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_preview_returned(self) -> None:
        comic = _make_comic()
        with (
            patch.object(
                AdminTagWritePreflightView,
                "resolve_comic_pks",
                return_value=frozenset({comic.pk}),
            ),
            patch(_VIEW_COMICBOX_TARGET, _PreviewComicbox),
        ):
            response = self.client.post(
                _PREFLIGHT_URL,
                data={"collection": "comics", "pks": [str(comic.pk)], "patch": "{}"},
                content_type="application/json",
            )
        assert response.status_code == HTTPStatus.OK
        # The API wraps responses in a {data, meta, errors} envelope and
        # camelCases keys.
        body = response.json()["data"]
        previews = body["filenamePreviews"]
        assert len(previews) == 1
        assert previews[0]["old"] == "c.cbz"
        assert previews[0]["new"] == _PREVIEW_NAME
        assert body["rename"] is False

    def test_preview_lists_every_comic(self) -> None:
        count = 3
        comics = _make_comics(count)
        pks = frozenset(c.pk for c in comics)
        with (
            patch.object(
                AdminTagWritePreflightView, "resolve_comic_pks", return_value=pks
            ),
            patch(_VIEW_COMICBOX_TARGET, _PreviewComicbox),
        ):
            response = self.client.post(
                _PREFLIGHT_URL,
                data={
                    "collection": "comics",
                    "pks": [str(c.pk) for c in comics],
                    "patch": "{}",
                },
                content_type="application/json",
            )
        body = response.json()["data"]
        previews = body["filenamePreviews"]
        assert len(previews) == count
        assert {p["old"] for p in previews} == {"c0.cbz", "c1.cbz", "c2.cbz"}
        assert all(p["new"] == _PREVIEW_NAME for p in previews)
        assert body["total"] == count


class TagByIdRenamePropagationTests(TestCase):
    """rename on the task flows into the enqueued BulkTagWriteTask."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_user": "u", "metron_password": "p"}
        )
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.manager = OnlineTagSessionManager(  # pyright: ignore[reportUninitializedInstanceVariable]
            _double(logger), _double(self.queue), thread_queue=None
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_rename_propagates_to_write(self) -> None:
        comic = _make_comic()
        tags = {"series": "X", "identifiers": {"metron": {"key": "123"}}}
        task = OnlineTagByIdTask(
            comic_pk=comic.pk, source="metron", issue_id=123, rename=True
        )
        with patch(_FETCH_TARGET, return_value=tags):
            self.manager.tag_by_id(task)
        writes = [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        assert len(writes) == 1
        assert writes[0].rename is True


class _DeferredPrompt:
    """Minimal deferred-prompt stand-in for _serialize_prompt."""

    fingerprint = "fp"
    path = Path("/x/c.cbz")
    source = "metron"
    candidates: ClassVar[list] = []
    mode = "update"


class SerializePromptRenameTests(SimpleTestCase):
    """Deferred prompts carry the rename flag so resolution honors it."""

    def test_rename_stored(self) -> None:
        result = OnlineTagSessionManager._serialize_prompt(  # noqa: SLF001
            _DeferredPrompt(),
            1,
            ("COMIC_INFO",),
            delete_original=False,
            rename=True,
        )
        assert result["rename"] is True
