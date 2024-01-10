"""Generated by Django 4.0 on 2021-12-17 04:36."""


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Indexes for filtered and sorted comic fields."""

    dependencies = [
        ("codex", "0007_auto_20211210_1710"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comic",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="format",
            field=models.CharField(db_index=True, max_length=16, null=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="parent_folder",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="codex.folder",
            ),
        ),
        migrations.AlterField(
            model_name="comic",
            name="read_ltr",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="year",
            field=models.PositiveSmallIntegerField(db_index=True, null=True),
        ),
    ]
