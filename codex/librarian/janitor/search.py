"""Clean up the search tables."""
from codex.librarian.status import librarian_status_done, librarian_status_update
from codex.models import SearchQuery
from codex.serializers.browser import BrowserPageSerializer
from codex.settings.logging import get_logger


# Keep the last thousand
LIMIT = BrowserPageSerializer.NUM_AUTOCOMPLETE_QUERIES * 100
CLEAN_SEARCH_STATUS_KEYS = {"type": "Cleanup Old Search Queries"}
LOG = get_logger(__name__)


def clean_old_queries():
    """Clean up old autoqueries."""
    librarian_status_update(CLEAN_SEARCH_STATUS_KEYS, 0, None)
    delete_pks = SearchQuery.objects.order_by("-used_at")[LIMIT:].values_list(
        "pk", flat=True
    )
    delete_sqs = SearchQuery.objects.filter(pk__in=delete_pks)
    count, _ = delete_sqs.delete()
    librarian_status_done([CLEAN_SEARCH_STATUS_KEYS])
    LOG.verbose(f"Deleted {count} old search queries.")
