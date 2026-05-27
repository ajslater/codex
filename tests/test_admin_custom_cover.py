"""Tests for the admin custom-cover endpoints."""

from __future__ import annotations

import io
import json
from http import HTTPStatus
from pathlib import Path
from typing import Final, override
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from PIL import Image

from codex.choices.notifications import Notifications
from codex.models import CustomCover, Imprint, Publisher, Series, Volume
from codex.settings import CUSTOM_COVERS_UPLOADS_DIR

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_QUEUE_PATCH = "codex.views.admin.custom_cover.LIBRARIAN_QUEUE"


def _v4(response):
    """Unwrap the v4 ``{data, meta, errors}`` envelope and return ``data``."""
    body = response.json()
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body


def _png_bytes(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(name: str = "cover.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _png_bytes(), content_type="image/png")


class AdminCustomCoverUploadTestCase(TestCase):
    """Cover ``/admin/custom-covers`` upload, validation, and listing."""

    @override
    def setUp(self) -> None:
        """Provision an admin client and a target Publisher row."""
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin-cc", email="cc@example.com", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.login(username="admin-cc", password=_TEST_PASSWORD)
        self.publisher: Publisher = Publisher.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="Marvel", sort_name="marvel"
        )

    @patch(_QUEUE_PATCH)
    def test_upload_happy_path(self, mock_queue) -> None:
        """A valid PNG creates the row, writes to uploads/, links the group."""
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        assert response.status_code == HTTPStatus.CREATED
        pk = _v4(response)["customCoverPk"]
        cover = CustomCover.objects.get(pk=pk)
        assert cover.group == "p"
        assert cover.library_id is None  # pyright: ignore[reportAttributeAccessIssue]
        assert cover.path.startswith(str(CUSTOM_COVERS_UPLOADS_DIR))
        # Naming convention: ``{group_char}-{pk}-{slug}.{ext}``. Sortable
        # by group on disk and trivially scannable for a given linked
        # group; slug uses the linked row's sort_name.
        filename = Path(cover.path).name
        assert filename.startswith(f"p-{pk}-")
        assert filename.endswith(".png")
        assert "marvel" in filename
        self.publisher.refresh_from_db()
        assert self.publisher.custom_cover_id == pk  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        # COVERS notification fans out to the WebSocket so connected
        # browsers refresh the changed card without a manual reload.
        # The v4 factory enriches each enqueue with a fresh mtime, so
        # check the text rather than identity-comparing the singleton.
        enqueued = [call.args[0] for call in mock_queue.put.call_args_list]
        assert any(
            getattr(t, "text", None) == Notifications.COVERS.value for t in enqueued
        )

    @patch(_QUEUE_PATCH)
    def test_non_admin_forbidden(self, mock_queue) -> None:  # noqa: ARG002
        """A non-staff session is rejected with 401/403."""
        User.objects.create_user(
            username="plain", email="p@example.com", password=_TEST_PASSWORD
        )
        client = Client()
        client.login(username="plain", password=_TEST_PASSWORD)
        response = client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        assert response.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}

    @patch(_QUEUE_PATCH)
    @patch(
        "codex.views.admin.custom_cover.get_custom_cover_max_upload_bytes",
        return_value=10,
    )
    def test_oversize_upload_rejected(self, mock_bytes, mock_queue) -> None:  # noqa: ARG002
        """Uploads over the byte cap return a 400 and write nothing."""
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={
                "group": "p",
                "pks": str(self.publisher.pk),
                "image": _upload(),
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert not CustomCover.objects.exists()

    @patch(_QUEUE_PATCH)
    def test_non_image_rejected(self, mock_queue) -> None:  # noqa: ARG002
        """An upload that isn't a real image returns 400."""
        bogus = SimpleUploadedFile(
            "fake.png", b"not really png bytes", content_type="image/png"
        )
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": bogus},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @patch(_QUEUE_PATCH)
    def test_group_pk_mismatch_rejected(self, mock_queue) -> None:  # noqa: ARG002
        """``group=s`` with a Publisher pk fails fast with 400."""
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "s", "pks": str(self.publisher.pk), "image": _upload()},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @patch(_QUEUE_PATCH)
    def test_remove_unlinks_and_purges(self, mock_queue) -> None:  # noqa: ARG002
        """``POST /admin/custom-covers/bulk-delete`` clears the FK and GCs orphans."""
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        pk = _v4(response)["customCoverPk"]
        response = self.client.post(
            "/api/v4/admin/custom-covers/bulk-delete",
            data=json.dumps({"group": "p", "pks": str(self.publisher.pk)}),
            content_type="application/json",
        )
        assert response.status_code == HTTPStatus.NO_CONTENT
        self.publisher.refresh_from_db()
        assert self.publisher.custom_cover_id is None  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        assert not CustomCover.objects.filter(pk=pk).exists()

    @patch(_QUEUE_PATCH)
    def test_delete_endpoint_removes_row(self, mock_queue) -> None:  # noqa: ARG002
        """``DELETE /admin/custom-covers/{pk}`` drops the row and the link."""
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        pk = _v4(response)["customCoverPk"]
        response = self.client.delete(f"/api/v4/admin/custom-covers/{pk}")
        assert response.status_code == HTTPStatus.NO_CONTENT
        assert not CustomCover.objects.filter(pk=pk).exists()

    @patch(_QUEUE_PATCH)
    def test_list_endpoint_returns_linked_group(self, mock_queue) -> None:  # noqa: ARG002
        """``GET /admin/custom-covers`` includes the linked group name."""
        upload_response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        assert upload_response.status_code == HTTPStatus.CREATED
        response = self.client.get("/api/v4/admin/custom-covers")
        assert response.status_code == HTTPStatus.OK
        rows = _v4(response)
        assert len(rows) == 1
        row = rows[0]
        assert row["group"] == "p"
        assert row["linkedGroupName"] == "Marvel"

    @patch(_QUEUE_PATCH)
    def test_replace_displaces_prior_cover(self, mock_queue) -> None:  # noqa: ARG002
        """A second upload to the same group purges the previous CustomCover."""
        first = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        first_pk = _v4(first)["customCoverPk"]
        second = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "p", "pks": str(self.publisher.pk), "image": _upload()},
        )
        second_pk = _v4(second)["customCoverPk"]
        assert second_pk != first_pk
        assert not CustomCover.objects.filter(pk=first_pk).exists()
        self.publisher.refresh_from_db()
        assert self.publisher.custom_cover_id == second_pk  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]


class CustomCoverVolumeSupportTestCase(TestCase):
    """Volume can now own a custom cover (regression check)."""

    @override
    def setUp(self) -> None:
        """Make a Volume row and an admin client."""
        publisher = Publisher.objects.create(name="P", sort_name="p")
        imprint = Imprint.objects.create(name="I", sort_name="i", publisher=publisher)
        self.series = Series.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name="S",
            sort_name="s",
            publisher=publisher,
            imprint=imprint,
        )
        self.volume: Volume = Volume.objects.create(  # pyright: ignore[reportUninitializedInstanceVariable]
            name=1,
            publisher=publisher,
            imprint=imprint,
            series=self.series,
        )
        self.admin = User.objects.create_superuser(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin-vol", email="vol@example.com", password=_TEST_PASSWORD
        )
        self.client = Client()
        self.client.login(username="admin-vol", password=_TEST_PASSWORD)

    @patch(_QUEUE_PATCH)
    def test_volume_upload(self, mock_queue) -> None:  # noqa: ARG002
        """Upload with ``group=v`` binds the Volume's ``custom_cover_id``."""
        response = self.client.post(
            "/api/v4/admin/custom-covers/upload",
            data={"group": "v", "pks": str(self.volume.pk), "image": _upload()},
        )
        assert response.status_code == HTTPStatus.CREATED
        self.volume.refresh_from_db()
        assert (
            self.volume.custom_cover_id == _v4(response)["customCoverPk"]  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        )


pytestmark = pytest.mark.django_db
