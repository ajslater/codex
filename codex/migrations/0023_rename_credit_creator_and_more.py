"""Generated by Django 4.1.7 on 2023-03-26 20:32."""
from pathlib import Path

from django.db import migrations, models

NEW_FILE_TYPE_SUFFIXES = frozenset(("cbz", "cbr", "cbt", "cbx"))


def prepare_librarianstatus(apps, _schema_editor):
    """Delete all librarian statuses for re-creation."""
    ls_model = apps.get_model("codex", "librarianstatus")
    ls_model.model.objects.all().delete()


def prepare_bookmarks(apps, _schema_editor):
    """Change bookmark fit_to to new values."""
    bookmark_model = apps.get_model("codex", "bookmark")
    bookmarks = bookmark_model.objects.exclude(fit_to="")
    for bookmark in bookmarks:
        bookmark.fit_to = bookmark.fit_to[0]
    bookmark_model.objects.bulk_update(bookmarks, fields=["fit_to"])


def prepare_comics(apps, _schema_editor):
    """Prepare comics for field choice changes."""
    comic_model = apps.get_model("codex", "comic")

    ## Comic.file_type
    comics = comic_model.objects.filter().only("path", "file_format")
    for comic in comics:
        if comic.file_format == "PDF":
            comic.file_format = "P"
            continue
        suffix = Path(comic.path).suffix[1:].lower() if comic.path else ""
        if suffix in NEW_FILE_TYPE_SUFFIXES:
            comic.file_format = suffix[-1].upper()
        else:
            comic.file_format = ""
    comic_model.objects.bulk_update(comics, fields=["file_format"])


def prepare_adminflags(apps, _schema_editor):
    """Migrate update flag data."""
    af_model = apps.get_model("codex", "adminflag")
    flags = af_model.objects.all()
    delete_pks = []
    update_flags = []
    for flag in flags:
        if "Folder" in flag.name:
            flag.name = "FV"
        elif "Registration" in flag.name:
            flag.name = "RG"
        elif "Users" in flag.name:
            flag.name = "NU"
        elif "Update" in flag.name:
            flag.name = "AU"
        elif "Search" in flag.name:
            flag.name = "SO"
        else:
            delete_pks.append(flag.pk)
        update_flags.append(flag)
    af_model.objects.filter(pk__in=delete_pks).delete()
    af_model.objects.bulk_update(update_flags, fields=("name",))


def prepare_timestamps(apps, _schema_editor):
    """Migrate timestamp data."""
    ts_model = apps.get_model("codex", "timestamp")
    timestamps = ts_model.objects.all()
    update_timestamps = []
    delete_pks = []
    for ts in timestamps:
        if "Covers" in ts.name:
            ts.name = "CV"
        elif "Janitor" in ts.name:
            ts.name = "JA"
        elif "Version" in ts.name:
            ts.name = "VR"
        elif "Search" in ts.name:
            ts.name = "SI"
        elif "API" in ts.name:
            ts.name = "AP"
        else:
            delete_pks.append(ts.pk)
            continue
        update_timestamps.append(ts)

    ts_model.objects.filter(pk__in=delete_pks).delete()
    ts_model.objects.bulk_update(update_timestamps, fields=("name",))


class Migration(migrations.Migration):
    """Prepare data and then migrate schema."""

    dependencies = [
        ("codex", "0022_bookmark_vertical_useractive_null_statuses"),
    ]

    operations = [
        # PREPARE
        migrations.RunPython(prepare_adminflags),
        migrations.RunPython(prepare_timestamps),
        migrations.RunPython(prepare_bookmarks),
        migrations.RunPython(prepare_comics),
        # RENAME MODELS
        migrations.RenameModel(
            old_name="Credit",
            new_name="Creator",
        ),
        migrations.RenameModel(
            old_name="CreditPerson",
            new_name="CreatorPerson",
        ),
        migrations.RenameModel(
            old_name="CreditRole",
            new_name="CreatorRole",
        ),
        # ADMIN FLAG
        migrations.RenameField(
            model_name="adminflag",
            old_name="name",
            new_name="key",
        ),
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("FV", "Folder View"),
                    ("RG", "Registration"),
                    ("NU", "Non Users"),
                    ("AU", "Auto Update"),
                    ("SO", "Search Index Optimize"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
        # TIMESTAMP
        migrations.RenameField(
            model_name="timestamp",
            old_name="name",
            new_name="key",
        ),
        migrations.AlterField(
            model_name="timestamp",
            name="key",
            field=models.CharField(
                choices=[
                    ("CV", "Covers"),
                    ("JA", "Janitor"),
                    ("VR", "Codex Version"),
                    ("SI", "Search Index UUID"),
                    ("AP", "API Key"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
        # LIBRARIAN STATUS
        migrations.RenameField(
            model_name="librarianstatus",
            old_name="name",
            new_name="subtitle",
        ),
        migrations.AlterUniqueTogether(
            name="librarianstatus",
            unique_together=set(),
        ),
        migrations.RenameField(
            model_name="librarianstatus",
            old_name="type",
            new_name="status_type",
        ),
        migrations.AlterField(
            model_name="librarianstatus",
            name="status_type",
            field=models.CharField(
                choices=[
                    ("CCC", "Create Covers"),
                    ("CCD", "Purge Covers"),
                    ("CFO", "Find Orphan"),
                    ("IDM", "Dirs Moved"),
                    ("IFM", "Files Moved"),
                    ("ITR", "Aggregate Tags"),
                    ("ITQ", "Query Missing Fks"),
                    ("ITC", "Create Fks"),
                    ("IDU", "Dirs Modified"),
                    ("IFU", "Files Modified"),
                    ("IFC", "Files Created"),
                    ("IMQ", "Query M2M Fields"),
                    ("IMC", "Link M2M Fields"),
                    ("IDD", "Dirs Deleted"),
                    ("IFD", "Files Deleted"),
                    ("IFI", "Failed Imports"),
                    ("JTD", "Cleanup Fk"),
                    ("JCU", "Codex Update"),
                    ("JCR", "Codex Restart"),
                    ("JCS", "Codex Stop"),
                    ("JDO", "Db Optimize"),
                    ("JDB", "Db Backup"),
                    ("JSD", "Cleanup Sessions"),
                    ("SIX", "Search Index Clear"),
                    ("SIU", "Search Index Update"),
                    ("SID", "Search Index Remove"),
                    ("SIM", "Search Index Merge"),
                    ("WPO", "Poll"),
                ],
                db_index=True,
                max_length=3,
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="librarianstatus",
            unique_together={("status_type", "subtitle")},
        ),
        # BOOKMARK
        migrations.AlterField(
            model_name="bookmark",
            name="fit_to",
            field=models.CharField(
                blank=True,
                choices=[
                    ("S", "Screen"),
                    ("W", "Width"),
                    ("H", "Height"),
                    ("O", "Orig"),
                ],
                default="",
                max_length=1,
            ),
        ),
        # COMIC
        migrations.RenameField(
            model_name="comic",
            old_name="credits",
            new_name="creators",
        ),
        migrations.RenameField(
            model_name="comic",
            old_name="format",
            new_name="original_format",
        ),
        migrations.RenameField(
            model_name="comic", old_name="file_format", new_name="file_type"
        ),
        migrations.AlterField(
            model_name="comic",
            name="file_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Z", "Cbz"),
                    ("R", "Cbr"),
                    ("T", "Cbt"),
                    ("X", "Cbx"),
                    ("P", "Pdf"),
                ],
                default="",
                max_length=1,
            ),
        ),
        migrations.AlterField(
            model_name="comic",
            name="comments",
            field=models.TextField(default=""),
        ),
        migrations.AlterField(
            model_name="comic",
            name="notes",
            field=models.TextField(default=""),
        ),
        migrations.AlterField(
            model_name="comic",
            name="summary",
            field=models.TextField(default=""),
        ),
    ]
