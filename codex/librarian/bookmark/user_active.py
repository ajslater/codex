"""Mixin for recording user active entry."""

from datetime import timedelta

from django.contrib.auth.models import User
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
        """Update user active timestamp on the user's :class:`UserAuth` row."""
        # Offline because profile gets hit rapidly in succession.
        try:
            last_recorded = self._user_active_recorded.get(pk, EPOCH_START)
            now = django_timezone.now()
            if now - last_recorded > self.USER_ACTIVE_RESOLUTION:
                user = User.objects.get(pk=pk)
                # update_or_create touches ``updated_at`` via auto_now on
                # BaseModel; the row also carries the per-user age-rating
                # ceiling but that stays untouched here.
                UserAuth.objects.update_or_create(user=user)
                self._user_active_recorded[pk] = now
        except User.DoesNotExist:
            pass
        except Exception as exc:
            reason = f"Update user activity {exc}"
            log.warning(reason)
