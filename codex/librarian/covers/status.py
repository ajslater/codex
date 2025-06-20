"""Cover status types."""

from django.db.models import TextChoices


class CoverStatusTypes(TextChoices):
    """Cover Types."""

    CREATE_COVERS = "CCC"
    PURGE_COVERS = "CCD"
    FIND_ORPHAN_COVERS = "CFO"
