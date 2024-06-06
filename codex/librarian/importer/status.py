"""Librarian Status for imports."""

from django.db.models import Choices


class ImportStatusTypes(Choices):
    """Keys for Import tasks."""

    DIRS_MOVED = "IDM"
    FILES_MOVED = "IFM"
    AGGREGATE_TAGS = "ITR"
    QUERY_MISSING_FKS = "ITQ"
    CREATE_FKS = "ITC"
    DIRS_MODIFIED = "IDU"
    FILES_MODIFIED = "IFU"
    FILES_CREATED = "IFC"
    QUERY_M2M_FIELDS = "IMQ"
    LINK_M2M_FIELDS = "IMC"
    DIRS_DELETED = "IDD"
    FILES_DELETED = "IFD"
    FAILED_IMPORTS = "IFI"
    QUERY_MISSING_COVERS = "ICQ"
    COVERS_MOVED = "ICM"
    COVERS_MODIFIED = "ICU"
    COVERS_CREATED = "ICC"
    COVERS_DELETED = "ICD"
    COVERS_LINK = "ICL"
    GROUP_UPDATE = "IGU"
    ADOPT_FOLDERS = "IAF"
