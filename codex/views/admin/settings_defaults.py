"""Admin site default browser and reader settings."""

from django.db import transaction
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import ADMIN_FLAGS_CHANGED_TASK
from codex.models import SettingsDefaults
from codex.serializers.admin.settings_defaults import SettingsDefaultsSerializer
from codex.settings.db import get_browser_defaults, get_reader_defaults
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.settings_defaults_catchup import (
    apply_to_anonymous,
    reach_counts,
)


def _payload(row: SettingsDefaults) -> dict:
    """Return the stored defaults plus the read-only factory values."""
    return {
        **SettingsDefaultsSerializer(row).data,
        "factory": SettingsDefaultsSerializer(SettingsDefaults()).data,
    }


def _broadcast() -> None:
    """Tell every client to refetch /session, whose defaultsRev changed."""
    LIBRARIAN_QUEUE.put(ADMIN_FLAGS_CHANGED_TASK)


class AdminSettingsDefaultsView(AdminAPIView):
    """GET/PUT for the SettingsDefaults singleton."""

    def get(self, _request):
        """Return the site defaults and the factory values."""
        row, _ = SettingsDefaults.objects.get_or_create(pk=1)
        return Response(_payload(row))

    def put(self, request):
        """
        Update the site defaults, and optionally catch up anonymous rows.

        ``applyToAnonymous`` moves the anonymous rows still holding the old
        resolved default, inside the same transaction as the save: the old
        values are only in hand until the save commits.
        """
        apply = bool(request.data.get("apply_to_anonymous"))
        with transaction.atomic():
            row, _ = SettingsDefaults.objects.get_or_create(pk=1)
            serializer = SettingsDefaultsSerializer(
                row, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            old_browser, old_reader = get_browser_defaults(), get_reader_defaults()
            serializer.save()
            applied = (
                apply_to_anonymous(
                    old_browser,
                    get_browser_defaults(),
                    old_reader,
                    get_reader_defaults(),
                )
                if apply
                else None
            )
            # After commit, so a client refetching /session never reads the
            # old defaultsRev and skips its reload.
            transaction.on_commit(_broadcast)
        payload = _payload(row)
        if applied is not None:
            payload["applied"] = applied
        return Response(payload)


class AdminSettingsDefaultsReachView(AdminAPIView):
    """GET how many anonymous rows still hold each current site default."""

    def get(self, _request):
        """Count the rows a catch-up could move, per field."""
        return Response(reach_counts(get_browser_defaults(), get_reader_defaults()))
