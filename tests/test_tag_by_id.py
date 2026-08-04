"""
Tests for tagging a comic by a known online issue id.

Tagging by id is not a separate endpoint: an id pinned per source rides along
in the ordinary start-session request, so a session can fetch the pinned
sources by id and search the rest in one lookup. Covered here: the identifier
parser (URL / ``source:id`` / bare ``4000-NNN`` / bare integer precedence), the
explicit-id config builder the stored-id prepass and prompt resolution share,
and the start endpoint's pinned-id validation + task enqueue.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

import pytest
from comicbox.online_session import OnlineCredentials
from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import Client, SimpleTestCase, TestCase

from codex.librarian.onlinetag.explicit_id import (
    _result_has_requested_id,
    build_explicit_id_config,
)
from codex.librarian.onlinetag.tasks import BulkOnlineTagTask
from codex.models import ComicboxTaggingDefaults
from codex.views.admin.identifier_parse import parse_identifier_input
from codex.views.admin.onlinetag import AdminOnlineTagStartView

_VIEW_QUEUE_TARGET: Final = "codex.views.admin.onlinetag.LIBRARIAN_QUEUE"
_START_URL: Final = "/api/v4/admin/tag-sessions/start"
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PK: Final = 7
_ISSUE_ID: Final = 12345
_CV_ISSUE_ID: Final = 456


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
        creds = OnlineCredentials(metron_key="t")
        settings = build_explicit_id_config("metron", 123, creds)
        assert settings.online.lookup.enabled is True
        assert dict(settings.online.lookup.ids) == {"metron": 123}
        assert settings.online.lookup.sources == ("metron",)
        assert settings.online.lookup.first_wins is True
        assert settings.online.auth.sources["metron"].key == "t"

    def test_build_explicit_id_config_passes_legacy_login(self) -> None:
        """A pre-API-key install still authenticates by explicit id."""
        creds = OnlineCredentials(metron_user="u", metron_password="p")  # noqa: S106
        settings = build_explicit_id_config("metron", 123, creds)
        auth = settings.online.auth.sources["metron"]
        assert auth.user == "u"
        assert auth.password == "p"  # noqa: S105

    def test_build_explicit_id_config_passes_the_comicvine_url(self) -> None:
        """Tagging by explicit id honors the custom Comic Vine endpoint."""
        creds = OnlineCredentials(
            comicvine_key="k", comicvine_url="https://cv.example.com/api"
        )
        settings = build_explicit_id_config("comicvine", 456, creds)
        auth = settings.online.auth.sources["comicvine"]
        assert auth.key == "k"
        assert auth.url == "https://cv.example.com/api"

    def test_build_explicit_id_config_merge(self) -> None:
        # Merge: both sources pinned by explicit id (primary first), first_wins
        # off, auth for both. comicbox runs every id-pinned source and merges.
        creds = OnlineCredentials(metron_key="t", comicvine_key="k")
        settings = build_explicit_id_config(
            "metron", 123, creds, extra_ids=(("comicvine", 456),)
        )
        assert settings.online.lookup.sources == ("metron", "comicvine")
        assert dict(settings.online.lookup.ids) == {"metron": 123, "comicvine": 456}
        assert settings.online.lookup.first_wins is False
        assert set(settings.online.auth.sources) == {"metron", "comicvine"}


def _make_admin() -> User:
    return User.objects.create_user(
        username="tag_by_id_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class TagByIdAuthTests(TestCase):
    """The start endpoint requires admin auth, pinned ids or not."""

    def test_anonymous_blocked(self) -> None:
        response = Client().post(
            _START_URL,
            data={"collection": "comics", "pks": ["1"], "ids": {"metron": "1"}},
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


class TagByIdStartViewTests(TestCase):
    """Pinned-id validation returns 400; a valid request enqueues the task."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        self.client = Client()
        self.client.force_login(_make_admin())
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_key": "t"},
        )

    def _post(self, ids: dict[str, str], sources: list[str] | None = None):
        data: dict = {"collection": "comics", "pks": [str(_PK)], "ids": ids}
        if sources is not None:
            data["sources"] = sources
        return self.client.post(_START_URL, data=data, content_type="application/json")

    def _post_resolving_one_comic(self, ids: dict[str, str], **kwargs):
        """Post with the comic resolution and queue stubbed; return the task."""
        with (
            patch.object(
                AdminOnlineTagStartView,
                "resolve_comic_pks",
                return_value=frozenset({_PK}),
            ),
            patch(_VIEW_QUEUE_TARGET) as mocked_queue,
        ):
            response = self._post(ids, **kwargs)
        assert response.status_code == HTTPStatus.ACCEPTED, response.content
        return mocked_queue.put.call_args.args[0]

    def test_no_credentials_returns_400(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={
                "metron_key": "",
                "metron_user": "",
                "metron_password": "",
                "comicvine_key": "",
            },
        )
        response = self._post({"metron": "1"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_legacy_login_still_counts_as_configured(self) -> None:
        """An install predating API keys can still tag by id."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1,
            defaults={"metron_key": "", "metron_user": "u", "metron_password": "p"},
        )
        task = self._post_resolving_one_comic({"metron": f"metron:{_ISSUE_ID}"})
        assert task.ids == {"metron": _ISSUE_ID}

    def test_unparseable_identifier_returns_400(self) -> None:
        response = self._post({"metron": "not-an-id"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unconfigured_source_returns_400(self) -> None:
        # Only Metron is configured; a Comic Vine id has no credentials.
        response = self._post({"comicvine": "comicvine:4000-1"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unknown_source_key_returns_400(self) -> None:
        response = self._post({"gcd": "123"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_id_for_another_source_returns_400(self) -> None:
        """A Comic Vine id filed under the Metron key is a mistake, not a hint."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "t", "comicvine_key": "k"}
        )
        response = self._post({"metron": "comicvine:4000-1"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_id_for_unselected_source_returns_400(self) -> None:
        """A pinned source that isn't being run would silently do nothing."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "t", "comicvine_key": "k"}
        )
        response = self._post({"comicvine": "4000-1"}, sources=["metron"])
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_multiple_comics_with_pinned_id_returns_400(self) -> None:
        """One issue id can't describe a multi-comic selection."""
        with patch.object(
            AdminOnlineTagStartView,
            "resolve_comic_pks",
            return_value=frozenset({_PK, _PK + 1}),
        ):
            response = self._post({"metron": f"metron:{_ISSUE_ID}"})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_blank_id_is_ignored(self) -> None:
        """An empty token is a cleared input, not a pin: plain search."""
        task = self._post_resolving_one_comic({"metron": "  "})
        assert task.ids == {}

    def test_success_enqueues_task_with_pinned_id(self) -> None:
        task = self._post_resolving_one_comic({"metron": f"metron:{_ISSUE_ID}"})
        assert isinstance(task, BulkOnlineTagTask)
        assert task.comic_pks == frozenset({_PK})
        assert task.ids == {"metron": _ISSUE_ID}

    def test_mixed_pin_and_search(self) -> None:
        """Metron pinned, Comic Vine unpinned: one task, one pinned source."""
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "t", "comicvine_key": "k"}
        )
        task = self._post_resolving_one_comic(
            {"metron": f"metron:{_ISSUE_ID}"}, sources=["metron", "comicvine"]
        )
        assert task.ids == {"metron": _ISSUE_ID}
        assert task.sources == ("metron", "comicvine")

    def test_both_sources_pinned(self) -> None:
        ComicboxTaggingDefaults.objects.update_or_create(
            pk=1, defaults={"metron_key": "t", "comicvine_key": "k"}
        )
        task = self._post_resolving_one_comic(
            {
                "metron": f"metron:{_ISSUE_ID}",
                "comicvine": f"4000-{_CV_ISSUE_ID}",
            },
            sources=["metron", "comicvine"],
        )
        assert task.ids == {"metron": _ISSUE_ID, "comicvine": _CV_ISSUE_ID}

    def test_bare_number_resolves_against_the_sole_configured_source(self) -> None:
        task = self._post_resolving_one_comic({"metron": str(_ISSUE_ID)})
        assert task.ids == {"metron": _ISSUE_ID}
