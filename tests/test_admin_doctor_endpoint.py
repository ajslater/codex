"""Integration tests for the /admin/doctor endpoint."""

from pathlib import Path
from typing import Final, override
from unittest.mock import patch

from comicbox.doctor import CheckResult, DoctorReport, Status
from django.contrib.auth.models import User
from django.test import Client, TestCase

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_URL: Final = "/api/v4/admin/doctor"
_HTTP_OK: Final = 200
_HTTP_FORBIDDEN: Final = 403

_REPORT = DoctorReport(
    header=("comicbox 5.3.0", "Python 3.14.4", "Linux-6.1", "Docker"),
    results=(
        CheckResult(
            "Archives", "CBR", Status.OK, found="rarfile 4.5", detail="via unrar"
        ),
        CheckResult(
            "Archives",
            "PDF",
            Status.WRONG_VERSION,
            found="comicbox-pdffile 0.6.3",
            detail="comicbox requires comicbox-pdffile~=1.0",
            fix="pip install 'comicbox-pdffile~=1.0'",
        ),
        CheckResult(
            "Config",
            "user config",
            Status.OK,
            found=Path("/home/abc/.config/comicbox/config.yaml"),
            detail="parsed",
        ),
    ),
)


def _data(response) -> dict:
    """Unwrap the v4 ``{data, meta, errors}`` envelope."""
    return response.json()["data"]


class DoctorAuthTestCase(TestCase):
    """The report names paths and versions, so only admins read it."""

    def test_anonymous_blocked(self) -> None:
        assert Client().get(_URL).status_code == _HTTP_FORBIDDEN

    def test_non_admin_blocked(self) -> None:
        User.objects.create_user(username="regular", password=_TEST_PASSWORD)
        client = Client()
        client.login(username="regular", password=_TEST_PASSWORD)
        assert client.get(_URL).status_code == _HTTP_FORBIDDEN


class DoctorReportTestCase(TestCase):
    """The rows arrive as plain strings with a problem count."""

    @override
    def setUp(self) -> None:
        User.objects.create_user(
            username="doctor_admin",
            password=_TEST_PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        self.client.login(username="doctor_admin", password=_TEST_PASSWORD)

    def test_report(self) -> None:
        with patch("codex.views.admin.doctor.run_doctor", return_value=_REPORT):
            response = self.client.get(_URL)
        assert response.status_code == _HTTP_OK
        data = _data(response)
        assert data["header"] == list(_REPORT.header)
        assert data["problems"] == 1
        pdf = data["results"][1]
        assert pdf == {
            "section": "Archives",
            "name": "PDF",
            # The enum's spelling, space included, not its member name.
            "status": "WRONG VERSION",
            "found": "comicbox-pdffile 0.6.3",
            "detail": "comicbox requires comicbox-pdffile~=1.0",
            "fix": "pip install 'comicbox-pdffile~=1.0'",
        }
        # A Path renders as its string.
        assert data["results"][2]["found"] == "/home/abc/.config/comicbox/config.yaml"
        assert data["results"][0]["fix"] == ""
