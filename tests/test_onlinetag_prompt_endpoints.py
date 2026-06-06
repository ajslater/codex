"""Integration tests for the session-agnostic online-tag prompt endpoints."""

from __future__ import annotations

from http import HTTPStatus
from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from codex.librarian.onlinetag.session_cache import set_pending_prompts
from codex.librarian.onlinetag.tasks import (
    OnlineTagPromptResponseTask,
    OnlineTagSkipAllPromptsTask,
)

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_PROMPTS_URL: Final = "/api/v4/admin/tag-prompts"
_QUEUE_TARGET: Final = "codex.views.admin.onlinetag.LIBRARIAN_QUEUE"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _make_admin() -> User:
    return User.objects.create_user(
        username="tag_prompts_admin",
        password=_TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
    )


def _prompt(fingerprint: str, pk: int) -> dict:
    return {
        "fingerprint": fingerprint,
        "pk": pk,
        "path": f"/c/{pk}.cbz",
        "source": "metron",
        "candidates": [],
        "mode": "auto",
        "formats": ["COMIC_INFO"],
        "delete_original": False,
    }


class TagPromptsAuthTestCase(TestCase):
    """The prompt endpoints require admin auth."""

    def test_anonymous_blocked(self) -> None:
        response = Client().get(_PROMPTS_URL)
        assert response.status_code == HTTPStatus.FORBIDDEN


class TagPromptsTestCase(TestCase):
    """List, resolve, and skip-all operate on the global pending-prompt cache."""

    @override
    def setUp(self) -> None:
        cache.clear()
        self.client = Client()  # pyright: ignore[reportUninitializedInstanceVariable]
        self.client.force_login(_make_admin())

    def test_lists_pending_prompts(self) -> None:
        set_pending_prompts({"fp1": _prompt("fp1", 1), "fp2": _prompt("fp2", 2)})

        response = self.client.get(_PROMPTS_URL)

        assert response.status_code == HTTPStatus.OK
        prompts = _v4(response)["prompts"]
        fingerprints = {p["fingerprint"] for p in prompts}
        assert fingerprints == {"fp1", "fp2"}

    def test_lists_empty_when_no_prompts(self) -> None:
        response = self.client.get(_PROMPTS_URL)

        assert response.status_code == HTTPStatus.OK
        assert _v4(response)["prompts"] == []

    def test_resolve_enqueues_task_by_fingerprint(self) -> None:
        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(
                f"{_PROMPTS_URL}/fp1",
                data={"action": "choose", "payload": "0"},
                content_type="application/json",
            )

        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, OnlineTagPromptResponseTask)
        assert task.prompt_fingerprint == "fp1"
        assert task.action == "choose"
        assert task.payload == 0
        assert task.chosen_volume_id is None

    def test_skip_all_enqueues_task(self) -> None:
        with patch(_QUEUE_TARGET) as mocked_queue:
            response = self.client.post(f"{_PROMPTS_URL}/skip-all")

        assert response.status_code == HTTPStatus.ACCEPTED
        task = mocked_queue.put.call_args.args[0]
        assert isinstance(task, OnlineTagSkipAllPromptsTask)
