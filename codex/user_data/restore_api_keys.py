"""
Restore API keys from the user-data sidecar.

Split out of :mod:`codex.user_data.restore`. The ``api_keys`` table holds
hashes only, which is all a key needs to log in again. A backup written
before keys were backed up has no rows here, and one written before Stats
API keys were per admin carries the server's plaintext key in the ``AK``
admin flag instead; that one is hashed into a stats key for the first admin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from codex.choices.api_key import ApiKeyScope

if TYPE_CHECKING:
    from codex.user_data.restore_shelves import RestoreReport
    from codex.user_data.store import SidecarStore

_TABLE: Final = "api_keys"
# The retired admin flag that held the server-wide Stats API key.
LEGACY_STATS_KEY_FLAG: Final = "AK"
LEGACY_STATS_KEY_NAME: Final = "Stats Key"


def _restore_one(row, report: RestoreReport) -> None:
    from django.contrib.auth import get_user_model

    from codex.models.api_key import UserApiKey

    username = row["username"]
    user = get_user_model().objects.filter(username=username).first()
    if user is None:
        report.note_skipped(_TABLE, f"missing user {username!r}")
        return
    if row["scope"] not in ApiKeyScope.values:
        report.note_skipped(_TABLE, f"unknown scope {row['scope']!r}")
        return
    if UserApiKey.objects.filter(digest=row["digest"]).exists():
        # Already here: a second restore, or a key that never left.
        report.note_written(_TABLE)
        return
    if UserApiKey.objects.filter(user=user, name=row["name"]).exists():
        report.note_skipped(
            _TABLE, f"user {username!r} already has a different key of that name"
        )
        return
    api_key = UserApiKey.objects.create(
        user=user,
        name=row["name"],
        scope=row["scope"],
        prefix=row["prefix"] or "",
        digest=row["digest"],
        kosync_digest=row["kosync_digest"] or "",
        last_used_at=row["last_used_at"] or None,
    )
    if row["created_at"]:
        # ``auto_now_add`` ignores a value passed to ``create``.
        UserApiKey.objects.filter(pk=api_key.pk).update(created_at=row["created_at"])
    report.note_written(_TABLE)


def restore_api_keys(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """
    Restore API key rows. Never replaces a key that is already here.

    Run after users. A row whose user is missing is skipped, as is one
    whose name the user already gave a different key.
    """
    for row in store.fetchall(_TABLE):
        if dry_run:
            report.note_written(_TABLE)
            continue
        _restore_one(row, report)


def _first_admin():
    """Return the lowest-pk active superuser, else active staff, else None."""
    from django.contrib.auth import get_user_model

    users = get_user_model().objects.filter(is_active=True).order_by("pk")
    return (
        users.filter(is_superuser=True).first() or users.filter(is_staff=True).first()
    )


def restore_legacy_stats_key(
    store: SidecarStore, report: RestoreReport, *, dry_run: bool
) -> None:
    """Hash an old backup's server-wide Stats API key into the first admin's."""
    from codex.models.api_key import UserApiKey, api_key_digest

    secret = next(
        (
            row["value"]
            for row in store.fetchall("admin_flags")
            if row["key"] == LEGACY_STATS_KEY_FLAG and row["value"]
        ),
        "",
    )
    if not secret:
        return
    if dry_run:
        report.note_written(_TABLE)
        return
    if UserApiKey.objects.filter(digest=api_key_digest(secret)).exists():
        report.note_written(_TABLE)
        return
    owner = _first_admin()
    if owner is None:
        report.note_skipped(_TABLE, "no admin to own the old Stats API key")
        return
    UserApiKey.adopt(owner, LEGACY_STATS_KEY_NAME, ApiKeyScope.STATS.value, secret)
    report.note_written(_TABLE)
