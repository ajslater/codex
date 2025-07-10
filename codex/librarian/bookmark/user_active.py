"""Mixin for recording user active entry."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone as django_timezone

from codex.models.admin import UserActive
from codex.views.const import EPOCH_START


class UserActiveMixin:
    """Record user active entry."""

    # only hit the disk to record user activity every so often
    USER_ACTIVE_RESOLUTION = timedelta(hours=1)

    def init_user_active(self):
        """Init the last recorded dict."""
        self._user_active_recorded = {}  # pyright: ignore[reportUninitializedInstanceVariable]

    def update_user_active(self, pk: int, log):
        """Update user active."""
        # Offline because profile gets hit rapidly in succession.
        try:
            last_recorded = self._user_active_recorded.get(pk, EPOCH_START)
            now = django_timezone.now()
            if now - last_recorded > self.USER_ACTIVE_RESOLUTION:
                user = User.objects.get(pk=pk)
                UserActive.objects.update_or_create(user=user)
                self._user_active_recorded[pk] = now
        except User.DoesNotExist:
            pass
        except Exception as exc:
            reason = f"Update user activity {exc}"
            log.warning(reason)
