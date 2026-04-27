"""
Regression tests for the admin user / group list endpoints.

Both serializers depend on viewset-level ``select_related`` to avoid
N+1 fan-out:

- :class:`codex.serializers.admin.users.UserSerializer` reads
  ``source="userauth.updated_at"`` and
  ``source="userauth.age_rating_metron"`` per row. The viewset
  must ``select_related("userauth__age_rating_metron")``.
- :class:`codex.serializers.admin.groups.GroupSerializer` reads
  ``source="groupauth.exclude"`` per row. The viewset must
  ``select_related("groupauth")``.

Without a regression test, a future refactor that splits the
queryset (or reorders the prefetch chain) silently regresses to
N+1. These tests pin the contract: query count for the list
endpoint stays bounded as the row count grows.
"""

from typing import Final, override

from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from codex.models.auth import GroupAuth, UserAuth

# Test-only password — short, fixed, and never deployed. Hush
# bandit's hardcoded-password warning at the call sites.
_TEST_PASSWORD: Final = "test-pw-hush-S106"  # noqa: S105
_HTTP_OK: Final = 200
# Admin list endpoints prefetch their auth FK row per query. The
# per-request setup (session + admin-flag fetches + ACL pipeline)
# plus the list query plus its prefetch should comfortably sit
# under this ceiling. A regression that drops ``select_related``
# fans out N additional queries per row, tripping the assertion.
_ADMIN_LIST_QUERY_CEILING: Final = 20


class AdminListQueryCountTestCase(TestCase):
    """Bound the per-row query count on /admin/user and /admin/group."""

    @override
    def setUp(self) -> None:
        """Create an admin + a small fixture set of users / groups."""
        self.admin = User.objects.create_user(  # pyright: ignore[reportUninitializedInstanceVariable]
            username="admin_query_count_admin",
            password=_TEST_PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        UserAuth.objects.create(user=self.admin)
        for i in range(3):
            user = User.objects.create_user(
                username=f"admin_query_count_user{i}", password=_TEST_PASSWORD
            )
            UserAuth.objects.create(user=user)
        for i in range(3):
            group = Group.objects.create(name=f"group{i}")
            GroupAuth.objects.create(group=group)

        self.client = Client()
        self.client.force_login(self.admin)

    def _query_count(self, url: str) -> int:
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        if response.status_code != _HTTP_OK:
            reason = f"GET {url} returned {response.status_code}: {response.content!r}"
            raise AssertionError(reason)
        return len(ctx.captured_queries)

    def test_admin_user_list_query_count(self) -> None:
        """
        Bound /admin/user list queries — fail-loud on N+1 regressions.

        A regression that drops
        ``select_related("userauth__age_rating_metron")`` would push
        the count by 2 per row (one ``userauth`` SELECT + one
        ``age_rating_metron`` SELECT), tripping the ceiling well
        before becoming visible to users.
        """
        count = self._query_count("/api/v3/admin/user")
        assert count <= _ADMIN_LIST_QUERY_CEILING, (
            f"Expected <= {_ADMIN_LIST_QUERY_CEILING} queries on /admin/user, "
            f"got {count}"
        )

    def test_admin_group_list_query_count(self) -> None:
        """
        Bound /admin/group list queries — fail-loud on N+1 regressions.

        A regression that drops ``select_related("groupauth")`` would
        add one query per group for the ``groupauth.exclude`` access,
        tripping the ceiling.
        """
        count = self._query_count("/api/v3/admin/group")
        assert count <= _ADMIN_LIST_QUERY_CEILING, (
            f"Expected <= {_ADMIN_LIST_QUERY_CEILING} queries on /admin/group, "
            f"got {count}"
        )
