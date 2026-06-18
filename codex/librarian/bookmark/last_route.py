"""Mixin for persisting the browser's last route."""

from collections.abc import Mapping

from django.utils import timezone as django_timezone

from codex.models.settings import SettingsBrowserLastRoute


class LastRouteUpdateMixin:
    """Write the deferred last-route update for a SettingsBrowser row."""

    def update_last_route(self, settings_pk: int, route: Mapping, log) -> None:
        """
        Update the route row with one statement, no fetch.

        ``filter().update()`` skips ``auto_now``, so stamp
        ``updated_at`` explicitly (same pattern as
        :meth:`UserActiveMixin.update_user_active`). Values arrive
        URL-validated from the browse view; a missing row means the
        SettingsBrowser was deleted between queue and flush — drop it.
        """
        pks = route.get("pks") or (0,)
        updated = SettingsBrowserLastRoute.objects.filter(
            browser_id=settings_pk
        ).update(
            collection=route.get("collection", "root"),
            pks=list(pks),
            page=route.get("page", 1),
            updated_at=django_timezone.now(),
        )
        if not updated:
            log.debug(f"No last-route row for settings {settings_pk}; skipped.")
