"""Admin Choices."""

from types import MappingProxyType

from django.db.models.enums import TextChoices

from codex.models.age_rating import SELECTABLE_RATINGS


class AdminFlagChoices(TextChoices):
    """Choices for Admin Flags."""

    ANONYMOUS_USER_AGE_RATING = "AA"
    AGE_RATING_DEFAULT = "AR"
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
        AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value: "Anonymous User Age Rating",
        AdminFlagChoices.AGE_RATING_DEFAULT.value: "Age Rating Default",
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

# Admin-facing selects only; excludes Unknown (treated as NULL at filter time).
METRON_AGE_RATING_CHOICES = MappingProxyType(
    {value: value for value in SELECTABLE_RATINGS}
)
