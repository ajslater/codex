"""Admin Choices."""

from types import MappingProxyType

from comicbox.config.online import Effort, MatchMode
from django.db.models.enums import TextChoices

from codex.librarian.onlinetag.sources import SUPPORTED_SOURCES


class AdminFlagChoices(TextChoices):
    """Choices for Admin Flags."""

    ANONYMOUS_USER_AGE_RATING = "AA"
    AGE_RATING_DEFAULT = "AR"
    AUTO_UPDATE = "AU"
    BANNER_TEXT = "BT"
    CUSTOM_COVER_MAX_UPLOAD_MB = "CM"
    FOLDER_VIEW = "FV"
    IMPORT_METADATA = "IM"
    KOREADER_SYNC = "KS"
    LAZY_IMPORT_METADATA = "LI"
    BROWSER_MAX_OBJ_PER_PAGE = "MP"
    NON_USERS = "NU"
    OPDS = "OP"
    REGISTRATION = "RG"
    REGISTER_VERIFICATION = "RV"
    STATS_API = "SA"
    SEND_TELEMETRY = "ST"


ADMIN_FLAG_CHOICES = MappingProxyType(
    {
        AdminFlagChoices.ANONYMOUS_USER_AGE_RATING.value: "Anonymous User Age Rating",
        AdminFlagChoices.AGE_RATING_DEFAULT.value: "Age Rating Default",
        AdminFlagChoices.AUTO_UPDATE.value: "Auto Update",
        AdminFlagChoices.BANNER_TEXT.value: "Banner Text",
        AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value: "Browser Page Size",
        AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value: (
            "Custom Cover Max Upload (MB)"
        ),
        AdminFlagChoices.FOLDER_VIEW.value: "Folder View",
        AdminFlagChoices.IMPORT_METADATA.value: "Import Tags on Library Scan",
        AdminFlagChoices.KOREADER_SYNC.value: "KOReader Sync",
        AdminFlagChoices.LAZY_IMPORT_METADATA.value: "Import Tags on Demand",
        AdminFlagChoices.NON_USERS.value: "Non Users",
        AdminFlagChoices.OPDS.value: "OPDS",
        AdminFlagChoices.REGISTRATION.value: "Registration",
        AdminFlagChoices.REGISTER_VERIFICATION.value: "Verify New User Email",
        AdminFlagChoices.STATS_API.value: "Stats API Keys",
        AdminFlagChoices.SEND_TELEMETRY.value: "Send Stats",
    }
)


TAGGING_CHOICES = MappingProxyType(
    {
        # comicbox's match modes, ask through eager, derived so the two
        # cannot drift. Ask prompts for every match instead of writing.
        "matchMode": MappingProxyType(
            {mode.value: mode.value.capitalize() for mode in MatchMode}
        ),
        "promptsMode": MappingProxyType(
            {
                "ask": "Ask",
                "never": "Never",
            }
        ),
        # How much API budget a comic may spend against a fan-out source.
        # Derived from comicbox's enum so the two cannot drift, plus the
        # empty choice comicbox spells as a null effort: unset, and so
        # still free to be dropped to minimal for a large run.
        "effort": MappingProxyType(
            {"": "Auto"}
            | {effort.value: effort.value.capitalize() for effort in Effort}
        ),
        # The online-tag sources codex can drive, in comicbox's priority
        # order: comicbox's names filtered to codex's registry, so a source
        # comicbox adds stays hidden until codex registers it.
        "sources": SUPPORTED_SOURCES,
    }
)

TAGGING_DEFAULTS = MappingProxyType(
    {
        "matchMode": "auto",
        "promptsMode": "ask",
        "effort": "",
    }
)
