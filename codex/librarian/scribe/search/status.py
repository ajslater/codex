"""Search Index Status Types."""

from django.db.models import TextChoices


class SearchIndexStatusTypes(TextChoices):
    """Search Index Status Types."""

    SEARCH_INDEX_CLEAR = "SIX"
    SEARCH_INDEX_SYNC_UPDATE = "SSU"
    SEARCH_INDEX_SYNC_CREATE = "SSC"
    SEARCH_INDEX_CLEAN = "SID"
    SEARCH_INDEX_OPTIMIZE = "SIO"
