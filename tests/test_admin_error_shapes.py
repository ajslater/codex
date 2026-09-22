"""
The wire shape of a 400, on both admin renderers.

The client has to normalize what the server sends before it can bind an
error to the field that caused it, so the shape is a contract rather
than an implementation detail. It is not the obvious one on either
renderer, and neither is documented anywhere else:

* Admin **resource** viewsets render through ``AdminJSONAPIRenderer``.
  For any 4xx ``get_resource_name`` returns ``"errors"`` and
  ``format_errors`` is literally ``return {"errors": data}`` -- so the
  body is ``{"errors": {"username": [...]}}``, a **dict**, not the
  JSON:API error *list* a reader would expect, because DJA's own
  exception handler is not installed.
* **Envelope** endpoints emit ``{"errors": [{status, title, detail}]}``
  where ``detail`` carries the field map.

Pinning both here first is what makes the frontend change safe.
"""

import json
from http import HTTPStatus
from typing import Final, override

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase

from codex.models import Library
from codex.startup import init_admin_flags
from tests.tmp_dirs import tmp_dir

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
TMP_DIR = tmp_dir("codex.tests.error_shapes")


class AdminErrorShapeTestCase(TestCase):
    """What a duplicate-name 400 actually looks like on the wire."""

    @override
    def setUp(self) -> None:
        """Log in an admin and seed one of each unique-named row."""
        init_admin_flags()
        TMP_DIR.mkdir(exist_ok=True, parents=True)
        User.objects.create_user(username="taken", password=_TEST_PASSWORD)
        Group.objects.create(name="taken")
        Library.objects.create(path=str(TMP_DIR))
        admin = User.objects.create_user(
            username="admin", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(admin)

    def _post(self, url: str, resource_type: str, attributes: dict):
        body = {"data": {"type": resource_type, "attributes": attributes}}
        return self.client.post(
            url, data=json.dumps(body), content_type="application/json"
        )

    def test_a_duplicate_username_is_a_field_keyed_dict(self) -> None:
        """
        Not a JSON:API error list.

        ``format_errors`` wraps the DRF dict verbatim, so the field map
        sits one level down under ``errors``. A client scanning the top
        level -- which is what ``getErrors`` did -- finds nothing and
        renders the whole object.
        """
        response = self._post(
            "/api/v4/admin/users",
            "users",
            {"username": "taken", "email": "", "password": _TEST_PASSWORD},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        body = response.json()
        assert isinstance(body["errors"], dict), body
        assert "username" in body["errors"], body
        assert isinstance(body["errors"]["username"], list), body

    def test_a_duplicate_group_name_has_the_same_shape(self) -> None:
        """Every admin resource viewset renders through the same renderer."""
        response = self._post("/api/v4/admin/groups", "groups", {"name": "taken"})

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        body = response.json()
        assert "name" in body["errors"], body

    def test_a_duplicate_library_path_has_the_same_shape(self) -> None:
        """
        ``Library.path`` is unique and ModelSerializer attaches the validator.

        No explicit ``UniqueValidator`` is written anywhere in codex, so
        this is DRF's automatic one -- which means the server side of
        uniqueness needs no change at all.
        """
        response = self._post(
            "/api/v4/admin/libraries", "libraries", {"path": str(TMP_DIR)}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        body = response.json()
        assert "path" in body["errors"], body

    def test_an_envelope_endpoint_nests_the_field_map_in_detail(self) -> None:
        """
        The other shape, and the reason one normalizer is not enough.

        ``EnvelopeJSONRenderer`` emits a JSON:API-ish error *list*, so
        the field map is at ``errors[0].detail`` rather than at
        ``errors``.
        """
        response = self.client.put(
            "/api/v4/admin/email-settings",
            data=json.dumps({"port": 0}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        body = response.json()
        assert isinstance(body["errors"], list), body
        detail = body["errors"][0]["detail"]
        assert isinstance(detail, dict), body
        assert "port" in detail, body
