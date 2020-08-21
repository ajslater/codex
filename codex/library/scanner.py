"""Scan root paths for comics."""
import logging
import os

from datetime import datetime
from pathlib import Path

from django.utils import timezone

from codex.models import Comic
from codex.models import RootPath

from .importer import import_comic


LOG = logging.getLogger(__name__)


def scan_add(root_path, force=False):
    """Add or update comics from a root path."""
    LOG.info(f"Scanning {root_path.path}")
    num_created = 0
    num_updated = 0
    num_skipped = 0
    num_passed = 0
    for root, dirnames, filenames in os.walk(root_path.path):
        rp = Path(root)
        LOG.debug(f"Scanning {rp}")
        for filename in sorted(filenames):
            path = rp / filename
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
            if root_path.last_scan is None or mtime > root_path.last_scan or force:
                created = import_comic(root_path, path)
                if created is None:
                    num_skipped += 1
                elif created:
                    num_created += 1
                else:
                    num_updated += 1
            else:
                num_passed += 1

    LOG.info(
        f"Created {num_created} comics."
        f" Updated {num_updated} comics."
        f" Skipped {num_passed} unmodified comics."
        f" Skipped {num_skipped} non-comic files."
    )


def scan_missing(root_path_id):
    """Look for missing comics."""
    comics_removed = 0
    comics = Comic.objects.filter(root_path=root_path_id, deleted_at=None)
    for comic in comics:
        if comic.path and not Path(comic.path).exists():
            comic.deleted_at = timezone.now()
            comics_removed += 1
            LOG.debug(
                f"Marked {comic.volume.series.name} v{comic.volume.name} "
                f"#{comic.issue:03} missing"
            )
    LOG.info(f"Marked {comics_removed} comics missing.")


def scan_root(root_path, force=False):
    """Scan a root path."""
    LOG.info(f"Scanning {root_path.path}...")
    scan_add(root_path, force)
    scan_missing(root_path)
    root_path.last_scan = timezone.now()
    root_path.save()


def scan_all(force=False):
    """Scan all root paths."""
    LOG.info("Scanning all root paths...")
    rps = RootPath.objects.all().filter(deleted_at=None)
    for root_path in rps:
        scan_root(root_path, force)
