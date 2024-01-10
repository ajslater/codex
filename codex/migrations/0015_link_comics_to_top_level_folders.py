"""Fix no parent folder comics."""
from pathlib import Path

from django.db import migrations


def fix_no_parent_folder_comics(apps, _schema_editor):
    """Add a parent folder to orphan comics."""
    folder_model = apps.get_model("codex", "folder")
    top_folders = folder_model.objects.filter(parent_folder=None).only("path")
    comic_model = apps.get_model("codex", "comic")
    orphan_comics = comic_model.objects.filter(parent_folder=None).only(
        "parent_folder", "path"
    )

    update_comics = []
    if orphan_comics:
        print(f"\nfixing {len(orphan_comics)} orphan comics.")
    for comic in orphan_comics:
        for folder in top_folders:
            if Path(comic.path).is_relative_to(folder.path):
                comic.parent_folder = folder
                print(f"linking {comic.path} to {folder.path}")
                update_comics.append(comic)
                break

    count = comic_model.objects.bulk_update(update_comics, ["parent_folder"])
    if count:
        print(f"updated {count} comics.")


class Migration(migrations.Migration):
    """Fix top level comics."""

    dependencies = [("codex", "0014_pdf_issue_suffix_remove_cover_image_sort_name")]

    operations = [
        migrations.RunPython(fix_no_parent_folder_comics),
    ]
