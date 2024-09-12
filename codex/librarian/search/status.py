"""Search Index Status Types."""

from django.db.models import Choices


class SearchIndexStatusTypes(Choices):
    """Search Index Status Types."""

    SEARCH_INDEX_CLEAR = "SIX"
    SEARCH_INDEX_UPDATE = "SIU"
    SEARCH_INDEX_CREATE = "SIC"
    SEARCH_INDEX_REMOVE = "SID"
    SEARCH_INDEX_OPTIMIZE = "SIO"
