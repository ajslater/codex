"""Mixin for recording user active entry."""

from datetime import timedelta

from django.utils import timezone as django_timezone

from codex.models.auth import UserAuth
from codex.views.const import EPOCH_START


class UserActiveMixin:
    """Record user active entry."""

    # only hit the disk to record user activity every so often
    USER_ACTIVE_RESOLUTION = timedelta(hours=1)

    def init_user_active(self) -> None:
        """Init the last recorded dict."""
        self._user_active_recorded = {}  # pyright: ignore[reportUninitializedInstanceVariable]

    def update_user_active(self, pk: int, log) -> None:
        """
        Update user active timestamp on the user's :class:`UserAuth` row.

        ``UserAuth`` rows are provisioned by the User ``post_save`` signal
        in :mod:`codex.signals.django_signals` for every creation path
        (admin UI, ``createsuperuser``, fixtures), and existing users were
        backfilled by migration 0039, so the row is guaranteed to exist
        for any logged-in pk reaching the bookmark thread.
        ``filter().update()`` is one round trip vs the prior
        ``User.objects.get`` + ``update_or_create`` (which fired
        SELECT + SELECT + UPDATE-or-INSERT). Mirrors the
        ``UserAuth`` / ``GroupAuth`` write-path pattern from
        admin-views-perf PR #610.

        ``auto_now=True`` on ``BaseModel.updated_at`` only fires on
        ``save()`` — ``.update()`` skips it — so pass the timestamp
        explicitly. A missing row remains a silent no-op with a warning
        — at this point it points to a real data integrity issue worth
        surfacing.
        """
        last_recorded = self._user_active_recorded.get(pk, EPOCH_START)
        now = django_timezone.now()
        if now - last_recorded <= self.USER_ACTIVE_RESOLUTION:
            return
        try:
            updated = UserAuth.objects.filter(user_id=pk).update(updated_at=now)
        except Exception as exc:
            log.warning(f"Update user activity {exc}")
            return
        if not updated:
            log.warning(f"No UserAuth row for user pk={pk}; skipping touch.")
        self._user_active_recorded[pk] = now
