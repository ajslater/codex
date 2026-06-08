"""
Tests for tagging a comic by a known online issue id.

Covers the three layers the feature adds: the identifier parser (URL /
``source:id`` / bare ``4000-NNN`` / bare integer precedence), the session
manager's ``tag_by_id`` (fetch → write, or surface a not-found), and the admin
endpoint's validation + task enqueue.
"""

from __future__ import annotations

import shutil
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final, override
from unittest.mock import patch

import pytest
from comicbox.online_session import OnlineCredentials
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
from loguru import logger

from codex.librarian.onlinetag.explicit_id import (
    _result_has_requested_id,
    build_explicit_id_config,
)
from codex.librarian.onlinetag.session_manager import OnlineTagSessionManager
from codex.librarian.onlinetag.tasks import OnlineTagByIdTask
from codex.librarian.scribe.tagwrite_errors import get_tag_write_errors
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
from codex.views.admin.identifier_parse import parse_identifier_input
from codex.views.admin.tagwrite import AdminTagByIdView

_TMP_DIR: Final = Path("/tmp/codex.tests.tagbyid")  # noqa: S108
_FETCH_TARGET: Final = (
    "codex.librarian.onlinetag.session_manager.fetch_tags_by_explicit_id"
)
_VIEW_QUEUE_TARGET: Final = "codex.views.admin.tagwrite.LIBRARIAN_QUEUE"
_TAG_BY_ID_URL: Final = "/api/v4/admin/tag-by-id"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PK: Final = 7
_ISSUE_ID: Final = 12345


class ParseIdentifierInputTests(SimpleTestCase):
    """The identifier parser resolves the source and numeric issue id."""

    def test_metron_prefixed(self) -> None:
        assert parse_identifier_input("metron:12345") == ("metron", 12345)

    def test_comicvine_prefixed_long(self) -> None:
        assert parse_identifier_input("comicvine:4000-67890") == ("comicvine", 67890)

    def test_comicvine_bare_long_code(self) -> None:
        # A bare 4000-NNN is self-identifying as Comic Vine, no prefix needed.
        assert parse_identifier_input("4000-67890") == ("comicvine", 67890)

    def test_comicvine_issue_url(self) -> None:
        url = "https://comicvine.gamespot.com/the-issue/4000-67890/"
        assert parse_identifier_input(url) == ("comicvine", 67890)

    def test_metron_numeric_url(self) -> None:
        # A trailing slash leaves a "12345/" key; the parser strips it.
        assert parse_identifier_input("https://metron.cloud/issue/12345/") == (
            "metron",
            12345,
        )

    def test_comicvine_volume_url_rejected(self) -> None:
        url = "https://comicvine.gamespot.com/the-vol/4050-12345/"
        with pytest.raises(ValueError, match="not an issue"):
            parse_identifier_input(url)

    def test_metron_slug_url_rejected(self) -> None:
        with pytest.raises(ValueError, match="numeric"):
            parse_identifier_input("https://metron.cloud/issue/superman-1/")

    def test_bare_int_uses_hint(self) -> None:
        assert parse_identifier_input("12345", source_hint="comicvine") == (
            "comicvine",
            12345,
        )

    def test_bare_int_sole_configured_source(self) -> None:
        got = parse_identifier_input("12345", configured_sources=frozenset({"metron"}))
        assert got == ("metron", 12345)

    def test_bare_int_ambiguous_raises(self) -> None:
        with pytest.raises(ValueError, match="could be Metron or Comic Vine"):
            parse_identifier_input(
                "12345", configured_sources=frozenset({"metron", "comicvine"})
            )

    def test_unknown_source_prefix_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown source"):
            parse_identifier_input("gcd:123")

    def test_unsupported_source_url_rejected(self) -> None:
        # A known comicbox domain (GCD) that doesn't support online id tagging.
        with pytest.raises(ValueError, match="aren't supported"):
            parse_identifier_input("https://www.comics.org/issue/12345/")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="Enter a Metron"):
            parse_identifier_input("   ")


class ExplicitIdHelpersTests(SimpleTestCase):
    """Success detection and config building for the explicit-id fetch."""

    def test_result_has_requested_id_match(self) -> None:
        tags = {"identifiers": {"metron": {"key": "123"}}}
        assert _result_has_requested_id(tags, "metron", 123) is True

    def test_result_has_requested_id_comicvine_long_key(self) -> None:
        tags = {"identifiers": {"comicvine": {"key": "4000-67890"}}}
        assert _result_has_requested_id(tags, "comicvine", 67890) is True

    def test_result_has_requested_id_mismatch(self) -> None:
        tags = {"identifiers": {"metron": {"key": "999"}}}
        assert _result_has_requested_id(tags, "metron", 123) is False

    def test_result_has_requested_id_missing(self) -> None:
        assert _result_has_requested_id({}, "metron", 123) is False

    def test_build_explicit_id_config_sets_ids(self) -> None:
        creds = OnlineCredentials(metron_user="u", metron_password="p")  # noqa: S106
        settings = build_explicit_id_config("metron", 123, creds)
        assert settings.online.lookup.enabled is True
        assert dict(settings.online.lookup.ids) == {"metron": 123}
        assert settings.online.lookup.sources == frozenset({"metron"})
        assert "metron" in settings.online.auth.sources


def _double(stub: object) -> Any:
    """Pass a test double through the manager's strictly-typed seams."""
    return stub


class _FakeQueue:
    """Collects everything put on it for assertions."""

    def __init__(self) -> None:
        self.items: list = []

    def put(self, item) -> None:
        self.items.append(item)


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
    path.touch()
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


class TagByIdSessionManagerTests(TestCase):
    """tag_by_id fetches the issue and enqueues a write, or surfaces failure."""

    @override
    def setUp(self) -> None:
        cache.clear()
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_user": "u", "metron_password": "p"},
        )
        self.queue = _FakeQueue()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.manager = OnlineTagSessionManager(  # pyright: ignore[reportUninitializedInstanceVariable]
            _double(logger),
            _double(self.queue),
            thread_queue=None,
        )

    @override
    def tearDown(self) -> None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def test_success_enqueues_write(self) -> None:
        comic = _make_comic()
        tags = {"series": "X", "identifiers": {"metron": {"key": "123"}}}
        task = OnlineTagByIdTask(comic_pk=comic.pk, source="metron", issue_id=123)

        with patch(_FETCH_TARGET, return_value=tags):
            self.manager.tag_by_id(task)

        writes = [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        assert len(writes) == 1
        assert writes[0].comic_pks == frozenset({comic.pk})
        assert writes[0].per_comic_patches == {comic.pk: tags}

    def test_not_found_records_error_and_skips_write(self) -> None:
        comic = _make_comic()
        task = OnlineTagByIdTask(comic_pk=comic.pk, source="metron", issue_id=999)

        with patch(_FETCH_TARGET, return_value=None):
            self.manager.tag_by_id(task)

        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]
        errors = get_tag_write_errors()
        assert errors
        assert errors[0]["path"] == str(comic.path)

    def test_missing_source_credentials_skips_fetch(self) -> None:
        comic = _make_comic()
        # Only Metron is configured; a Comic Vine request must not fetch.
        task = OnlineTagByIdTask(comic_pk=comic.pk, source="comicvine", issue_id=1)

        with patch(_FETCH_TARGET) as fetch:
            self.manager.tag_by_id(task)

        fetch.assert_not_called()
        assert not [i for i in self.queue.items if isinstance(i, BulkTagWriteTask)]

    def test_unknown_comic_skips_fetch(self) -> None:
        task = OnlineTagByIdTask(comic_pk=999999, source="metron", issue_id=1)

        with patch(_FETCH_TARGET) as fetch:
            self.manager.tag_by_id(task)

        fetch.assert_not_called()
        assert not self.queue.items


def _make_admin() -> User:
    return User.objects.create_user(
        username="tag_by_id_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class TagByIdViewAuthTests(TestCase):
    """The tag-by-id endpoint requires admin auth."""

    def test_anonymous_blocked(self) -> None:
        response = Client().post(
            _TAG_BY_ID_URL,
            data={"collection": "comics", "pk": "1", "identifier": "metron:1"},
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


class TagByIdViewTests(TestCase):
    """Validation paths return 400; a valid request enqueues the task."""

    @override
    def setUp(self) -> None:
        cache.clear()
        self.client = Client()
        self.client.force_login(_make_admin())
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_user": "u", "metron_password": "p"},
        )

    def _post(self, identifier: str, source: str | None = None):
        data: dict[str, str] = {
            "collection": "comics",
            "pk": str(_PK),
            "identifier": identifier,
        }
        if source is not None:
            data["source"] = source
        return self.client.post(
            _TAG_BY_ID_URL, data=data, content_type="application/json"
        )

    def test_no_credentials_returns_400(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_user": "", "metron_password": "", "comicvine_key": ""},
        )
        response = self._post("metron:1")
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unparseable_identifier_returns_400(self) -> None:
        response = self._post("not-an-id")
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unconfigured_source_returns_400(self) -> None:
        # Only Metron is configured; a Comic Vine id has no credentials.
        response = self._post("comicvine:4000-1")
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_success_enqueues_task(self) -> None:
        with (
            patch.object(
                AdminTagByIdView, "resolve_comic_pks", return_value=frozenset({_PK})
            ),
            patch(_VIEW_QUEUE_TARGET) as mocked_queue,
        ):
            response = self._post(f"metron:{_ISSUE_ID}")

        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, OnlineTagByIdTask)
        assert task.comic_pk == _PK
        assert task.source == "metron"
        assert task.issue_id == _ISSUE_ID
