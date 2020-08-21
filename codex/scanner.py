import logging
import os

from pathlib import Path

from .importer import import_comic
from .models import Comic
from .models import RootPath


LOG = logging.getLogger(__name__)


def scan_root(lib_root):
    comics_imported = 0
    LOG.info(f"Scanning {lib_root}")
    for root, dirnames, filenames in os.walk(lib_root):
        root_path = Path(root)
        LOG.debug(f"Scanning {root_path}")
        for filename in sorted(filenames):
            path = root_path / filename
            success = import_comic(path)
            if success:
                comics_imported += 1


def mark_missing(lib_root):
    comics_removed = 0
    comics = Comic.objects.get(root_path=lib_root.id)
    for comic in comics:
        if not Path(comics.path).exists():
            comic.path = None
            comics_removed += 1
            LOG.debug(f"Marked {comic.series} #{comic.issue:03} missing")


def scan_all():
    roots = RootPath.objects.all()
    for root_path in roots:
        scan_root(root_path)
        mark_missing(root_path)
