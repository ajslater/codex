"""Test harness for running individual modules."""
import sys

from codex.librarian.covers.coverd import CoverCreator
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.logger.mp_queue import LOG_QUEUE
from codex.models import Comic


def _test(limit):
    """Recreate all covers."""
    all_pks = Comic.objects.all().values_list("pk", flat=True)[:limit]
    cc = CoverCreator(LOG_QUEUE, LIBRARIAN_QUEUE)
    cc.bulk_create_comic_covers(all_pks)


def main():
    """Run the test function."""
    limit = int(sys.argv[1])
    print(limit)
    _test(limit)


if __name__ == "__main__":
    main()
