"""Generated by Django 3.1.1 on 2020-09-18 01:46."""
from django.db import migrations


class Migration(migrations.Migration):
    """Update verbose names."""

    dependencies = [
        ("codex", "0004_failedimport"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="comic",
            options={"verbose_name": "Issue"},
        ),
        migrations.AlterModelOptions(
            name="series",
            options={"verbose_name_plural": "Series"},
        ),
    ]
