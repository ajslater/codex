"""Cover status types."""

from django.db.models import Choices


class CoverStatusTypes(Choices):
    """Cover Types."""

    CREATE_COVERS = "CCC"
    PURGE_COVERS = "CCD"
    FIND_ORPHAN = "CFO"
