"""Generated by Django 4.0.2 on 2022-03-25 23:16."""

from decimal import Decimal

from django.db import migrations, models


def cast_issue_count(apps, _schema_editor):
    """Round issue counts to integer."""
    volume_model = apps.get_model("codex", "volume")
    volumes = volume_model.objects.filter(issue_count_decimal__isnull=False).only(
        "name", "issue_count_decimal", "issue_count"
    )
    update_volumes = []
    for volume in volumes:
        try:
            volume.issue_count = round(volume.issue_count_decimal)
            update_volumes.append(volume)
        except Exception:
            reason = (
                f"unable to cast volume {volume.name} "
                f"issue_count {volume.old_issue_count} to int"
            )
            print(reason)

    volume_model.objects.bulk_update(update_volumes, ("issue_count",))


class Migration(migrations.Migration):
    """Larger valid fields."""

    dependencies = [
        ("codex", "0012_rename_description_comic_comments"),
    ]

    operations = [
        migrations.RenameField(
            model_name="volume", old_name="issue_count", new_name="issue_count_decimal"
        ),
        migrations.AddField(
            model_name="volume",
            name="issue_count",
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.RunPython(cast_issue_count),
        migrations.RemoveField(model_name="volume", name="issue_count_decimal"),
        migrations.AlterField(
            model_name="adminflag",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="character",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="comic",
            name="community_rating",
            field=models.DecimalField(
                db_index=True, decimal_places=2, default=None, max_digits=5, null=True
            ),
        ),
        migrations.AlterField(
            model_name="comic",
            name="cover_image",
            field=models.CharField(max_length=256, null=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="cover_path",
            field=models.CharField(max_length=4095),
        ),
        migrations.AlterField(
            model_name="comic",
            name="critical_rating",
            field=models.DecimalField(
                db_index=True, decimal_places=2, default=None, max_digits=5, null=True
            ),
        ),
        migrations.AlterField(
            model_name="comic",
            name="issue",
            field=models.DecimalField(
                db_index=True, decimal_places=2, default=Decimal(0), max_digits=10
            ),
        ),
        migrations.AlterField(
            model_name="comic",
            name="language",
            field=models.CharField(db_index=True, max_length=32, null=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="comic",
            name="path",
            field=models.CharField(db_index=True, max_length=4095),
        ),
        migrations.AlterField(
            model_name="comic",
            name="scan_info",
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name="comic",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
        migrations.AlterField(
            model_name="creditperson",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="creditrole",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="failedimport",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="failedimport",
            name="path",
            field=models.CharField(db_index=True, max_length=4095),
        ),
        migrations.AlterField(
            model_name="failedimport",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
        migrations.AlterField(
            model_name="folder",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="folder",
            name="path",
            field=models.CharField(db_index=True, max_length=4095),
        ),
        migrations.AlterField(
            model_name="folder",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
        migrations.AlterField(
            model_name="genre",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="imprint",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="imprint",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
        migrations.AlterField(
            model_name="location",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="publisher",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="publisher",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
        migrations.AlterField(
            model_name="series",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="series",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
        migrations.AlterField(
            model_name="seriesgroup",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="storyarc",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="tag",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="team",
            name="name",
            field=models.CharField(db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name="volume",
            name="name",
            field=models.CharField(db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="volume",
            name="sort_name",
            field=models.CharField(db_index=True, default="", max_length=130),
        ),
    ]
