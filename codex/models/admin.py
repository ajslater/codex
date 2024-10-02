"""Admin models."""

import base64
import uuid

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    Choices,
    DateTimeField,
    OneToOneField,
    PositiveSmallIntegerField,
    TextChoices,
)
from django.utils.translation import gettext_lazy as _

from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.watchdog.status import WatchdogStatusTypes
from codex.models.base import MAX_FIELD_LEN, MAX_NAME_LEN, BaseModel, max_choices_len

__all__ = ("AdminFlag", "LibrarianStatus", "Timestamp", "UserActive")


class AdminFlag(BaseModel):
    """Flags set by administrators."""

    class FlagChoices(Choices):
        """Choices for Admin Flags."""

        FOLDER_VIEW = "FV"
        REGISTRATION = "RG"
        NON_USERS = "NU"
        AUTO_UPDATE = "AU"
        IMPORT_METADATA = "IM"
        SEND_TELEMETRY = "ST"

    FALSE_DEFAULTS = frozenset({FlagChoices.AUTO_UPDATE})

    key = CharField(
        db_index=True,
        max_length=max_choices_len(FlagChoices),
        choices=FlagChoices.choices,
    )
    on = BooleanField(default=True)

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("key",)


class LibrarianStatus(BaseModel):
    """Active Library Tasks."""

    CHOICES = tuple(
        CoverStatusTypes.choices
        + ImportStatusTypes.choices
        + JanitorStatusTypes.choices
        + SearchIndexStatusTypes.choices
        + WatchdogStatusTypes.choices
    )

    status_type = CharField(
        db_index=True, max_length=max_choices_len(CHOICES), choices=CHOICES
    )
    preactive = BooleanField(default=False)
    complete = PositiveSmallIntegerField(null=True, default=None)
    total = PositiveSmallIntegerField(null=True, default=None)
    active = DateTimeField(null=True, default=None)
    subtitle = CharField(db_index=True, max_length=MAX_NAME_LEN)

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("status_type", "subtitle")
        verbose_name_plural = "LibrarianStatuses"


class Timestamp(BaseModel):
    """Timestamped Named Strings."""

    class TimestampChoices(TextChoices):
        """Choices for Timestamps."""

        JANITOR = "JA", _("Janitor")
        CODEX_VERSION = "VR", _("Codex Version")
        SEARCH_INDEX_UUID = "SI", _("Search Index UUID")
        API_KEY = "AP", _("API Key")
        TELEMETER_SENT = "TS", _("Telemeter Sent")

    key = CharField(
        db_index=True,
        max_length=max_choices_len(TimestampChoices),
        choices=TimestampChoices.choices,
    )
    version = CharField(max_length=MAX_FIELD_LEN, default="")

    @classmethod
    def touch(cls, choice):
        """Touch a timestamp."""
        cls.objects.get(key=choice.value).save()

    def save_uuid_version(self):
        """Create base64 uuid."""
        uuid_bytes = uuid.uuid4().bytes
        b64_bytes = base64.urlsafe_b64encode(uuid_bytes)
        self.version = b64_bytes.decode("utf-8").replace("=", "")
        self.save()

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("key",)

    def __str__(self):
        """Print name for choice."""
        return self.TimestampChoices(self.key).name


class UserActive(BaseModel):
    """User last active record."""

    user = OneToOneField(settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE)


class GroupAuth(BaseModel):
    """Extended Attributes for Groups."""

    group = OneToOneField(Group, db_index=True, on_delete=CASCADE)
    exclude = BooleanField(db_index=True, default=False)
