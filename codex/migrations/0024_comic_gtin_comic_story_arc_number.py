"""Generated by Django 4.2.1 on 2023-05-10 22:44."""


from django.db import migrations, models


class Migration(migrations.Migration):
    """Add fields."""

    dependencies = [
        ("codex", "0023_rename_credit_creator_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="comic",
            name="gtin",
            field=models.CharField(db_index=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="comic",
            name="story_arc_number",
            field=models.PositiveSmallIntegerField(db_index=True, null=True),
        ),
    ]
