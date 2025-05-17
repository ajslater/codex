"""Librarian Status for imports."""

from django.db.models import TextChoices


class ImportStatusTypes(TextChoices):
    """Keys for Import tasks."""

    MOVE_FOLDERS = "IDM"
    MOVE_COMICS = "IFM"
    READ_TAGS = "IRT"
    AGGREGATE_TAGS = "ITR"
    QUERY_MISSING_TAGS = "ITQ"
    CREATE_TAGS = "ITC"
    UPDATE_FOLDERS = "IDU"
    UPDATE_COMICS = "IFU"
    CREATE_COMICS = "IFC"
    PREPARE_TAG_LINKS = "IPL"
    LINK_COMICS_TO_TAGS = "IMC"
    REMOVE_FOLDERS = "IDD"
    REMOVE_COMICS = "IFD"
    MARK_FAILED_IMPORTS = "IFI"
    QUERY_MISSING_COVERS = "ICQ"
    MOVE_CUSTOM_COVERS = "ICM"
    UPDATE_CUSTOM_COVERS = "ICU"
    CREATE_CUSTOM_COVERS = "ICC"
    REMOVE_CUSTOM_COVERS = "ICD"
    LINK_CUSTOM_COVERS = "ICL"
    UPDATE_GROUP_TIMESTAMPS = "IGU"
    ADOPT_FOLDERS = "IAF"
