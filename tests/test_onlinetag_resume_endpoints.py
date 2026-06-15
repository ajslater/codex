"""Integration tests for the online-tag resume + dismiss endpoints."""

from __future__ import annotations

from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import Client, TestCase

from codex.librarian.onlinetag.session_cache import set_active_scan_id
from codex.librarian.onlinetag.session_snapshot import set_resume_state
from codex.librarian.onlinetag.tasks import (
    BulkOnlineTagTask,
    OnlineTagDismissTask,
)

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_RESUME_URL: Final = "/api/v4/admin/tag-sessions/resume"
_DISMISS_URL: Final = "/api/v4/admin/tag-sessions/dismiss"
_QUEUE_TARGET: Final = "codex.views.admin.onlinetag.LIBRARIAN_QUEUE"

_PARAMS: Final = {
    "sources": ["metron", "comicvine"],
    "mode": "auto",
    "prompts_mode": "ask",
    "effort": "balanced",
    "auto_threshold": 0.85,
    "delete_original": False,
    "merge_all_sources": False,
    "dry_run": False,
}


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _make_admin() -> User:
    return User.objects.create_user(
        username="tag_resume_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


class TagResumeAuthTestCase(TestCase):
    """The resume/dismiss endpoints require admin auth."""

    def test_anonymous_blocked(self) -> None:
        response = Client().post(_RESUME_URL)
        assert response.status_code == HTTPStatus.FORBIDDEN


class TagResumeTestCase(TestCase):
    """Resume rebuilds a scan from the stored resume descriptor."""

    @override
    def setUp(self) -> None:
        caches["default"].clear()
        caches["tagging"].clear()
        self.client = Client()
        self.client.force_login(_make_admin())

    def test_resume_enqueues_task_over_remaining_pks(self) -> None:
        remaining = [11, 22, 33]
        set_resume_state(_PARAMS, remaining)

        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(_RESUME_URL)

        assert response.status_code == HTTPStatus.ACCEPTED
        data = _v4(response)
        assert data["comicCount"] == len(remaining)
        assert data["sessionId"]
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, BulkOnlineTagTask)
        assert task.comic_pks == frozenset(remaining)
        # sources round-trips JSON as a list; the task carries a tuple.
        assert task.sources == ("metron", "comicvine")
        assert task.mode == "auto"
        assert task.prompts_mode == "ask"

    def test_resume_conflict_when_scan_active(self) -> None:
        set_resume_state(_PARAMS, [11])
        set_active_scan_id("live-scan")

        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(_RESUME_URL)

        assert response.status_code == HTTPStatus.CONFLICT
        mocked_queue.put.assert_not_called()

    def test_resume_bad_request_when_nothing_to_resume(self) -> None:
        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(_RESUME_URL)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mocked_queue.put.assert_not_called()

    def test_dismiss_enqueues_task(self) -> None:
        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(_DISMISS_URL)

        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, OnlineTagDismissTask)
