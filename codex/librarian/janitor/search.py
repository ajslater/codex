"""Clean up the search tables."""
from codex.models import SearchQuery
from codex.serializers.browser import BrowserPageSerializer
from codex.settings.logging import get_logger


# Keep the last thousand
LIMIT = BrowserPageSerializer.NUM_AUTOCOMPLETE_QUERIES * 100
LOG = get_logger(__name__)


def clean_old_queries():
    """Clean up old autoqueries."""
    delete_pks = SearchQuery.objects.order_by("-used_at")[LIMIT:].values_list(
        "pk", flat=True
    )
    delete_sqs = SearchQuery.objects.filter(pk__in=delete_pks)
    count, _ = delete_sqs.delete()
    LOG.verbose(f"Deleted {count} old search queries.")
