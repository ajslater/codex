"""Librarian Status for imports."""

from django.db.models import TextChoices


class ImportStatusTypes(TextChoices):
    """
    Keys for Import tasks.

    Actual text is taken by titlecasing the left side.
    """

    MOVE_FOLDERS = "IDM"
    MOVE_COMICS = "IFM"
    MOVE_CUSTOM_COVERS = "ICM"

    READ_TAGS = "IRT"

    AGGREGATE_TAGS = "ITR"

    QUERY_MISSING_TAGS = "IQT"
    QUERY_COMIC_UPDATES = "IQU"
    QUERY_TAG_LINKS = "IQL"
    QUERY_MISSING_COVERS = "ICQ"

    CREATE_TAGS = "ITC"
    UPDATE_TAGS = "ITU"
    UPDATE_CUSTOM_COVERS = "ICU"
    CREATE_CUSTOM_COVERS = "ICC"

    CREATE_COMICS = "IFC"
    UPDATE_COMICS = "IFU"

    LINK_COMICS_TO_TAGS = "ILT"
    LINK_CUSTOM_COVERS = "ICL"

    REMOVE_FOLDERS = "IDD"
    REMOVE_COMICS = "IFD"
    REMOVE_CUSTOM_COVERS = "ICD"

    MARK_FAILED_IMPORTS = "IFI"

    UPDATE_GROUP_TIMESTAMPS = "IGU"

    ADOPT_FOLDERS = "IAF"
