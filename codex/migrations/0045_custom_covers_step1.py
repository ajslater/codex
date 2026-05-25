"""
Custom cover schema — step 1.

* ``Volume`` gains the ``custom_cover`` FK that every other browser
  group already inherits from ``BrowserGroupModel``. Direct linking
  replaces the (now-removed) name-based legacy matching.
* ``CustomCover.group`` adds ``v`` to its choice list so Volume
  custom covers can be created.
* ``CustomCover.library`` becomes nullable so the upcoming data
  migration can detach uploads from the synthetic covers-only
  Library, which will then be deleted in step 3.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Custom cover schema step 1: nullable library, Volume FK, V choice."""

    dependencies = [
        ("codex", "0044_register_verification_admin_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="volume",
            name="custom_cover",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_DEFAULT,
                to="codex.customcover",
            ),
        ),
        migrations.AlterField(
            model_name="customcover",
            name="group",
            field=models.CharField(
                choices=[
                    ("p", "P"),
                    ("i", "I"),
                    ("s", "S"),
                    ("v", "V"),
                    ("a", "A"),
                    ("f", "F"),
                ],
                db_index=True,
                max_length=1,
            ),
        ),
        migrations.AlterField(
            model_name="customcover",
            name="library",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="codex.library",
            ),
        ),
    ]
