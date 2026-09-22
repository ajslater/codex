"""
Let a user turn the cover-card read-state marker off.

Browser cards show read, unread and in-progress state under each cover. The
issue that asked for it also asked for a way back to the plain look, so this
is a per-user, per-client display preference alongside ``custom_covers`` and
``dynamic_covers``.

It defaults on. Without the marker a finished comic is indistinguishable from
one never opened -- the defect the marker exists to fix -- so an existing row
should not have to opt in to a bug fix. ``AddField`` with a constant default
is metadata-only here, and every existing row reads True.

The preference governs pixels only. The state is always folded into each
card's accessible name, so turning it off never costs a screen-reader user
the information.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add SettingsBrowser.show_read_state, defaulting on."""

    dependencies = [
        ("codex", "0056_reap_pending_deletes_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="settingsbrowser",
            name="show_read_state",
            field=models.BooleanField(default=True),
        ),
    ]
