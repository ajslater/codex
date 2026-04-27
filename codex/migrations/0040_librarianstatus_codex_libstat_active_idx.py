"""Partial index for the active LibrarianStatus admin endpoint."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add codex_libstat_active_idx for /admin/librarian/status."""

    dependencies = [
        ("codex", "0039_metron_age_rating"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="librarianstatus",
            index=models.Index(
                condition=models.Q(
                    ("preactive__isnull", False),
                    ("active__isnull", False),
                    _connector="OR",
                ),
                fields=["preactive", "active"],
                name="codex_libstat_active_idx",
            ),
        ),
    ]
