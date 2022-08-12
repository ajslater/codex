"""Created by AJ on 2022-08-11 05 19:12."""
import os
import shutil

from pathlib import Path

from django.db import migrations


CONFIG_PATH = Path(os.environ.get("CODEX_CONFIG_DIR", Path.cwd() / "config"))
COVER_ROOT = CONFIG_PATH / "cache" / "covers"


def clear_covers(_apps, _schema_editor):
    """Remove old covers."""
    shutil.rmtree(COVER_ROOT)


class Migration(migrations.Migration):
    """Bigger Covers."""

    dependencies = [
        ("codex", "0016_remove_comic_cover_path_librarianstatus"),
    ]

    operations = [migrations.RunPython(clear_covers)]
