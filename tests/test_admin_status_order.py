"""
The live status feed must follow registration order, not pk order.

CursorPagination re-orders the queryset with its own ordering, so the
view's order_by is inert — the pagination class itself must order by
(preactive, active, pk). Regression test for the sidebar progress feed
showing import phases scrambled into row-creation order.
"""

from datetime import timedelta
from http import HTTPStatus
from typing import Final, override

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils.timezone import now

from codex.models import LibrarianStatus

_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_ACTIVE_URL: Final = "/api/v4/admin/tasks"
_ALL_URL: Final = "/api/v4/admin/tasks/all"
# Pipeline order deliberately different from the pk insertion order
# below: search (ISC) gets the lowest pk but the latest preactive.
_PIPELINE_ORDER: Final = ("IRT", "IAT", "IQT", "ICT", "ISC")


class AdminStatusOrderTestCase(TestCase):
    """Verify /admin/tasks ordering follows the registration stamps."""

    @override
    def setUp(self) -> None:
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admins", password=_TEST_PASSWORD, is_staff=True
        )
        self.client = Client()
        self.client.force_login(self.admin)
        LibrarianStatus.objects.all().delete()
        # Insert in reverse pipeline order so pk order is wrong on
        # purpose, then stamp preactive in pipeline order the way
        # status_controller.start_many does (now() + 100ms per index).
        registered = now()
        for status_type in reversed(_PIPELINE_ORDER):
            LibrarianStatus.objects.create(status_type=status_type, subtitle="")
        for index, status_type in enumerate(_PIPELINE_ORDER):
            LibrarianStatus.objects.filter(status_type=status_type).update(
                preactive=registered + timedelta(milliseconds=index * 100)
            )

    def _get_status_types(self, url: str) -> tuple[str, ...]:
        resp = self.client.get(url)
        assert resp.status_code == HTTPStatus.OK, resp.content
        results = resp.json()["data"]["results"]
        return tuple(row["statusType"] for row in results)

    def test_active_feed_orders_by_registration(self) -> None:
        """The sidebar poll lists statuses in import pipeline order."""
        assert self._get_status_types(_ACTIVE_URL) == _PIPELINE_ORDER

    def test_active_feed_null_preactive_sorts_first(self) -> None:
        """A started-but-never-registered row sorts above registered rows."""
        LibrarianStatus.objects.filter(status_type="ICT").update(
            preactive=None, active=now()
        )
        expected = ("ICT", "IRT", "IAT", "IQT", "ISC")
        assert self._get_status_types(_ACTIVE_URL) == expected

    def test_history_view_keeps_pk_order(self) -> None:
        """The Jobs tab full history stays in insertion order."""
        assert self._get_status_types(_ALL_URL) == tuple(reversed(_PIPELINE_ORDER))
