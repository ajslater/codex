"""Admin Choices."""

from types import MappingProxyType

from django.db.models.enums import TextChoices


class AdminFlagChoices(TextChoices):
    """Choices for Admin Flags."""

    AUTO_UPDATE = "AU"
    BANNER_TEXT = "BT"
    FOLDER_VIEW = "FV"
    IMPORT_METADATA = "IM"
    LAZY_IMPORT_METADATA = "LI"
    NON_USERS = "NU"
    REGISTRATION = "RG"
    SEND_TELEMETRY = "ST"


ADMIN_FLAG_CHOICES = MappingProxyType(
    {
        AdminFlagChoices.AUTO_UPDATE.value: "Auto Update",
        AdminFlagChoices.BANNER_TEXT.value: "Banner Text",
        AdminFlagChoices.FOLDER_VIEW.value: "Folder View",
        AdminFlagChoices.IMPORT_METADATA.value: "Import Metadata on Library Scan",
        AdminFlagChoices.LAZY_IMPORT_METADATA.value: "Import Metadata on Demand",
        AdminFlagChoices.NON_USERS.value: "Non Users",
        AdminFlagChoices.REGISTRATION.value: "Registration",
        AdminFlagChoices.SEND_TELEMETRY.value: "Send Stats",
    }
)
