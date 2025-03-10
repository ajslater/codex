"""Search Index Status Types."""

from django.db.models import TextChoices


class SearchIndexStatusTypes(TextChoices):
    """Search Index Status Types."""

    SEARCH_INDEX_CLEAR = "SIX"
    SEARCH_INDEX_UPDATE = "SIU"
    SEARCH_INDEX_CREATE = "SIC"
    SEARCH_INDEX_REMOVE = "SID"
    SEARCH_INDEX_OPTIMIZE = "SIO"
