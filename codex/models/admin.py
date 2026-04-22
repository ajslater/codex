"""Admin models."""

import base64
import uuid
from typing import override

from django.db.models import (
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    PositiveSmallIntegerField,
    TextChoices,
)
from django.utils.translation import gettext_lazy as _

from codex.choices.admin import AdminFlagChoices
from codex.choices.statii import ADMIN_STATUS_TITLES
from codex.models.age_rating import AgeRatingMetron
from codex.models.base import MAX_FIELD_LEN, MAX_NAME_LEN, BaseModel
from codex.models.choices import (
    max_choices_len,
    text_choices_from_map,
)

__all__ = ("AdminFlag", "LibrarianStatus", "Timestamp")


class AdminFlag(BaseModel):
    """
    Flags set by administrators.

    Some flag keys use the free-form :attr:`value` string (e.g. Banner Text),
    some use only the :attr:`on` boolean. The two age-rating flags
    (``AGE_RATING_DEFAULT``, ``ANONYMOUS_USER_AGE_RATING``) use
    :attr:`age_rating_metron` — a typed FK to the :class:`AgeRatingMetron`
    lookup table — so the ACL filter and the UI both operate on real rows
    instead of name strings. ``SET_NULL`` on delete: if the target metron
    row ever disappears, the flag falls back to its seeded default at the
    next boot.
    """

    FALSE_DEFAULTS = frozenset({AdminFlagChoices.AUTO_UPDATE})

    key = CharField(
        db_index=True,
        max_length=max_choices_len(AdminFlagChoices),
        choices=AdminFlagChoices.choices,
    )
    on = BooleanField(default=True)
    value = CharField(max_length=MAX_NAME_LEN, default="", blank=True)
    age_rating_metron = ForeignKey(
        AgeRatingMetron,
        db_index=True,
        null=True,
        blank=True,
        default=None,
        on_delete=SET_NULL,
    )

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("key",)


class LibrarianStatus(BaseModel):
    """Active Library Tasks."""

    StatusChoices = text_choices_from_map(
        ADMIN_STATUS_TITLES.inverse, "LibrarianStatusChoices"
    )

    status_type = CharField(
        db_index=True,
        max_length=max_choices_len(StatusChoices),
        choices=StatusChoices.choices,
    )
    subtitle = CharField(db_index=True, max_length=MAX_NAME_LEN)
    complete = PositiveSmallIntegerField(null=True, default=None)
    total = PositiveSmallIntegerField(null=True, default=None)
    preactive = DateTimeField(null=True, default=None)
    active = DateTimeField(null=True, default=None)

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("status_type", "subtitle")
        verbose_name_plural = "LibrarianStatuses"


class Timestamp(BaseModel):
    """Timestamped Named Strings."""

    class Choices(TextChoices):
        """Choices for Timestamps."""

        API_KEY = "AP", _("API Key")
        CODEX_VERSION = "VR", _("Codex Version")
        JANITOR = "JA", _("Janitor")
        TELEMETER_SENT = "TS", _("Telemeter Sent")

    key = CharField(
        db_index=True,
        max_length=max_choices_len(Choices),
        choices=Choices.choices,
    )
    version = CharField(max_length=MAX_FIELD_LEN, default="")

    @classmethod
    def touch(cls, choice) -> None:
        """Touch a timestamp."""
        cls.objects.get(key=choice.value).save()

    def save_uuid_version(self) -> None:
        """Create base64 uuid."""
        uuid_bytes = uuid.uuid4().bytes
        b64_bytes = base64.urlsafe_b64encode(uuid_bytes)
        self.version = b64_bytes.decode("utf-8").replace("=", "")
        self.save()

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("key",)

    @override
    def __repr__(self) -> str:
        """Print name for choice."""
        return self.Choices(self.key).name
