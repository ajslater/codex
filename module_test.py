"""Test harness for running individual modules."""
import os
import sys

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")
django.setup()
from codex.librarian.covers.create import bulk_create_comic_covers  # noqa: E402
from codex.models import Comic  # noqa: E402


def _test(limit):
    """Recreate all covers."""
    all_pks = Comic.objects.all().values_list("pk", flat=True)[:limit]
    bulk_create_comic_covers(all_pks)


def main():
    """Run the test function."""
    limit = int(sys.argv[1])
    print(limit)
    _test(limit)


if __name__ == "__main__":
    main()
