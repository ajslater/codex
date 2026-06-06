"""Admin models."""

from typing import override

from django.db.models import (
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    Index,
    JSONField,
    PositiveSmallIntegerField,
    Q,
    TextChoices,
    URLField,
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
from codex.models.fields import EncryptedCharField

__all__ = (
    "AdminFlag",
    "ComicboxTaggingDefaults",
    "EmailSettings",
    "LibrarianStatus",
    "ThrottleSettings",
    "Timestamp",
)


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

    FALSE_DEFAULTS = frozenset(
        {AdminFlagChoices.AUTO_UPDATE, AdminFlagChoices.REGISTER_VERIFICATION}
    )

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


class ComicboxTaggingDefaults(BaseModel):
    """Singleton model for default comicbox tagging options and credentials."""

    class MatchModeChoices(TextChoices):
        """Match mode options for online tagging (mirrors comicbox.MatchMode)."""

        CAREFUL = "careful", _("Careful")
        AUTO = "auto", _("Auto")
        EAGER = "eager", _("Eager")

    class PromptsModeChoices(TextChoices):
        """Prompt behavior options for online tagging."""

        ASK = "ask", _("Ask")
        NEVER = "never", _("Never")

    default_formats = JSONField(default=list)
    delete_original = BooleanField(default=False)
    default_match_mode = CharField(
        max_length=MAX_FIELD_LEN,
        choices=MatchModeChoices.choices,
        default=MatchModeChoices.AUTO,
    )
    default_prompts_mode = CharField(
        max_length=MAX_FIELD_LEN,
        choices=PromptsModeChoices.choices,
        default=PromptsModeChoices.ASK,
    )
    default_sources = JSONField(default=list)

    metron_user = EncryptedCharField()
    metron_password = EncryptedCharField()
    metron_url = URLField(max_length=256, blank=True, default="")
    comicvine_key = EncryptedCharField()
    comicvine_url = URLField(max_length=256, blank=True, default="")

    # Active session id + pending prompts used to live here. They are
    # transient operational state — they only matter while a tagging
    # job is in flight — so they moved to the Django cache. See
    # ``codex.librarian.onlinetag.session_state``.

    @override
    def save(self, *args, **kwargs):
        """Enforce singleton: always use pk=1."""
        self.pk = 1
        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        """Constraints."""

        verbose_name_plural = "ComicboxTaggingDefaults"


class EmailSettings(BaseModel):
    """
    Singleton SMTP configuration for outbound email.

    Read by :class:`codex.mail.DBEmailBackend` on each send so admin
    edits take effect on the next message without restart. When ``host``
    or ``from_address`` is blank the backend short-circuits to a no-op
    and feature gates (registration verification, password reset link)
    fall back to *off* — see :func:`codex.settings.db.email_enabled`.

    ``password`` is encrypted at rest via :class:`EncryptedCharField`
    using ``FIELD_ENCRYPTION_KEY``.
    """

    host = CharField(max_length=MAX_NAME_LEN, blank=True, default="")
    port = PositiveSmallIntegerField(default=587)
    user = CharField(max_length=MAX_NAME_LEN, blank=True, default="")
    password = EncryptedCharField()
    use_tls = BooleanField(default=True)
    use_ssl = BooleanField(default=False)
    timeout = PositiveSmallIntegerField(default=10)
    from_address = CharField(max_length=MAX_NAME_LEN, blank=True, default="")
    subject_prefix = CharField(max_length=MAX_FIELD_LEN, blank=True, default="[Codex] ")

    @override
    def save(self, *args, **kwargs):
        """Enforce singleton: always use pk=1."""
        self.pk = 1
        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        """Constraints."""

        verbose_name_plural = "EmailSettings"


class ThrottleSettings(BaseModel):
    """
    Singleton DRF rate-limit configuration.

    Each field is a positive integer rate in requests per minute (or
    per hour for ``reset_password``). ``0`` disables the limit for that
    scope. Read at request time by the DB-aware throttle classes in
    :mod:`codex.throttling` — admin edits take effect on the next
    request without a restart.
    """

    anon = PositiveSmallIntegerField(default=0)
    user = PositiveSmallIntegerField(default=0)
    opds = PositiveSmallIntegerField(default=0)
    opensearch = PositiveSmallIntegerField(default=0)
    reset_password = PositiveSmallIntegerField(default=5)

    @override
    def save(self, *args, **kwargs):
        """Enforce singleton: always use pk=1."""
        self.pk = 1
        super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        """Constraints."""

        verbose_name_plural = "ThrottleSettings"


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
        # The /admin/librarian/status endpoint filters
        # ``preactive IS NOT NULL OR active IS NOT NULL`` and orders by
        # ``preactive, active, pk``. A partial index on the matching rows
        # serves both the filter and the ORDER BY without scanning the
        # historical (both-NULL) rows.
        indexes = (
            Index(
                fields=("preactive", "active"),
                condition=Q(preactive__isnull=False) | Q(active__isnull=False),
                name="codex_libstat_active_idx",
            ),
        )


class Timestamp(BaseModel):
    """
    Keyed singleton holding a last-known ``value`` and an auto-updated ``updated_at``.

    Used by codex-version tracking, janitor last-run marker, and the
    telemeter install UUID + last-send marker. The API key used to
    live here too; it moved to :class:`AdminFlag` (key ``AK``) since
    it was the one row that was admin-managed configuration rather
    than internal operational state.
    """

    class Choices(TextChoices):
        """Choices for Timestamps."""

        CODEX_VERSION = "VR", _("Codex Version")
        JANITOR = "JA", _("Janitor")
        TELEMETER_SENT = "TS", _("Telemeter Sent")

    key = CharField(
        db_index=True,
        max_length=max_choices_len(Choices),
        choices=Choices.choices,
    )
    value = CharField(max_length=MAX_FIELD_LEN, default="")

    @classmethod
    def touch(cls, choice) -> None:
        """Touch a timestamp."""
        cls.objects.get(key=choice.value).save()

    class Meta(BaseModel.Meta):
        """Constraints."""

        unique_together = ("key",)

    @override
    def __repr__(self) -> str:
        """Print name for choice."""
        return self.Choices(self.key).name
