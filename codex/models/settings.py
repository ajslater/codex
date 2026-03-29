"""User/session settings models."""

from typing import override

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db.models import (
    CASCADE,
    PROTECT,
    SET_NULL,
    BooleanField,
    CharField,
    CheckConstraint,
    ForeignKey,
    JSONField,
    OneToOneField,
    PositiveSmallIntegerField,
    Q,
    TextChoices,
    UniqueConstraint,
)

from codex.choices.browser import (
    BROWSER_BOOKMARK_FILTER_CHOICES,
    BROWSER_ORDER_BY_CHOICES,
    BROWSER_ROUTE_CHOICES,
    BROWSER_TOP_GROUP_CHOICES,
)
from codex.models.base import MAX_NAME_LEN, BaseModel
from codex.models.choices import ReadingDirectionChoices, max_choices_len

__all__ = (
    "SettingsBrowser",
    "SettingsBrowserFilters",
    "SettingsBrowserLastRoute",
    "SettingsBrowserShow",
    "SettingsReader",
)


# Custom on_delete handlers
#
# Django's migration serializer resolves on_delete by module path + function
# name, so these must be proper top-level functions — not closures.


def cascade_if_session_null(
    collector,
    field,
    sub_objs,
    using,  # noqa: ARG001
):
    """
    Cascade delete only when the session FK is also null.

    Used as on_delete for the user FK.  When a user is deleted:
    - Rows where session is also null are orphaned to cascade delete.
    - Rows where session is set to just null out the user FK.
    """
    orphans = [obj for obj in sub_objs if obj.session_id is None]
    if orphans:
        collector.collect(
            orphans,
            source=field.remote_field.model,
            source_attr=field.name,
            nullable=field.null,
        )
    if field.null:
        collector.add_field_update(field, None, sub_objs)


def cascade_if_user_null(
    collector,
    field,
    sub_objs,
    using,  # noqa: ARG001
):
    """
    Cascade delete only when the user FK is also null.

    Used as on_delete for the session FK.  When a session is deleted:
    - Rows where user is also null are orphaned to cascade delete.
    - Rows where user is set to just null out the session FK.
    """
    orphans = [obj for obj in sub_objs if obj.user_id is None]
    if orphans:
        collector.collect(
            orphans,
            source=field.remote_field.model,
            source_attr=field.name,
            nullable=field.null,
        )
    if field.null:
        collector.add_field_update(field, None, sub_objs)


# Shared choices


class ClientChoices(TextChoices):
    """API vs OPDS client type."""

    API = "api", "API"
    OPDS = "opds", "OPDS"


class FitToChoices(TextChoices):
    """Reader fit-to choices."""

    SCREEN = "S"
    WIDTH = "W"
    HEIGHT = "H"
    ORIG = "O"


#################
# Abstract base #
#################


class SettingsBase(BaseModel):
    """Abstract base for per-user / per-session settings."""

    client = CharField(
        max_length=max_choices_len(ClientChoices),
        choices=ClientChoices.choices,
        default=ClientChoices.API,
        db_index=True,
    )
    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        db_index=True,
        on_delete=cascade_if_session_null,
        null=True,
        blank=True,
    )
    session = ForeignKey(
        Session,
        db_index=True,
        on_delete=cascade_if_user_null,
        null=True,
        blank=True,
    )

    class Meta(BaseModel.Meta):
        """Abstract base settings."""

        abstract = True

    @override
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}"
            f" client={self.client}"
            f" user={self.user!r}"
            f" session={self.session!r}>"
        )


#####################################
# Browser Settings — related models #
#####################################


class SettingsBrowserShow(BaseModel):
    """
    Show-group boolean grid.

    Shared across SettingsBrowser rows — created but never deleted.
    With 4 booleans there are at most 16 distinct rows (in practice ~6).
    """

    p = BooleanField(default=True)
    i = BooleanField(default=False)
    s = BooleanField(default=True)
    v = BooleanField(default=False)

    class Meta(BaseModel.Meta):
        """Browser show-flag settings."""

        verbose_name_plural = "browser show settings"
        constraints = (
            UniqueConstraint(
                fields=("p", "i", "s", "v"),
                name="unique_settingsbrowsershow_flags",
            ),
        )

    @override
    def __repr__(self) -> str:
        return f"<SettingsBrowserShow p={self.p} i={self.i} s={self.s} v={self.v}>"


class SettingsBrowserFilters(BaseModel):
    """
    Filter columns for a single SettingsBrowser row.

    One-to-one with SettingsBrowser — created and deleted together.
    """

    browser = OneToOneField(
        "codex.SettingsBrowser",
        on_delete=CASCADE,
        related_name="filters",
    )

    # Bookmark filter (choice, not a list of ints)
    bookmark = CharField(
        max_length=16,
        choices=tuple(BROWSER_BOOKMARK_FILTER_CHOICES.items()),
        default="",
        blank=True,
    )

    # Dynamic filters — each stores a list of ints.
    age_rating = JSONField(default=list)
    characters = JSONField(default=list)
    country = JSONField(default=list)
    credits = JSONField(default=list)
    critical_rating = JSONField(default=list)
    decade = JSONField(default=list)
    file_type = JSONField(default=list)
    genres = JSONField(default=list)
    identifier_source = JSONField(default=list)
    language = JSONField(default=list)
    locations = JSONField(default=list)
    monochrome = JSONField(default=list)
    original_format = JSONField(default=list)
    reading_direction = JSONField(default=list)
    series_groups = JSONField(default=list)
    stories = JSONField(default=list)
    story_arcs = JSONField(default=list)
    tagger = JSONField(default=list)
    tags = JSONField(default=list)
    teams = JSONField(default=list)
    universes = JSONField(default=list)
    year = JSONField(default=list)

    FILTER_KEYS = frozenset(
        {
            "bookmark",
            "age_rating",
            "characters",
            "country",
            "credits",
            "critical_rating",
            "decade",
            "file_type",
            "genres",
            "identifier_source",
            "language",
            "locations",
            "monochrome",
            "original_format",
            "reading_direction",
            "series_groups",
            "stories",
            "story_arcs",
            "tagger",
            "tags",
            "teams",
            "universes",
            "year",
        }
    )

    class Meta(BaseModel.Meta):
        """Browser filter settings."""

        verbose_name_plural = "browser filter settings"

    @override
    def __repr__(self) -> str:
        return f"<SettingsBrowserFilters browser_id={self.browser!r}>"


class SettingsBrowserLastRoute(BaseModel):
    """
    Last-route columns for a single SettingsBrowser row.

    One-to-one with SettingsBrowser — created and deleted together.
    """

    browser = OneToOneField(
        "codex.SettingsBrowser",
        on_delete=CASCADE,
        related_name="last_route",
    )

    group = CharField(
        max_length=1,
        choices=tuple(BROWSER_ROUTE_CHOICES.items()),
        default="r",
    )
    pks = JSONField(default=list)
    page = PositiveSmallIntegerField(default=1)

    class Meta(BaseModel.Meta):
        """Browser last-route settings."""

        verbose_name_plural = "browser last-route settings"

    @override
    def __repr__(self) -> str:
        return (
            f"<SettingsBrowserLastRoute"
            f" group={self.group} pks={self.pks} page={self.page}>"
        )


####################
# Browser Settings #
####################


class SettingsBrowser(SettingsBase):
    """Persisted browser settings."""

    name = CharField(max_length=MAX_NAME_LEN, default="", blank=True, db_index=True)

    # Browse state
    top_group = CharField(
        max_length=1,
        choices=tuple(BROWSER_TOP_GROUP_CHOICES.items()),
        default="p",
    )
    order_by = CharField(
        max_length=32,
        choices=tuple(BROWSER_ORDER_BY_CHOICES.items()),
        default="",
    )
    order_reverse = BooleanField(default=False)
    search = CharField(max_length=4095, default="", blank=True)

    # Display preferences
    custom_covers = BooleanField(default=True)
    dynamic_covers = BooleanField(default=True)
    twenty_four_hour_time = BooleanField(default=False)
    always_show_filename = BooleanField(default=False)

    # FK to shared show-flags row.
    show = ForeignKey(
        SettingsBrowserShow,
        on_delete=PROTECT,
        related_name="+",
    )

    # filters and last_route live in their own tables
    # linked back by OneToOneField with related_name="filters" / "last_route".

    DIRECT_KEYS = frozenset(
        {
            "top_group",
            "order_by",
            "order_reverse",
            "custom_covers",
            "dynamic_covers",
            "twenty_four_hour_time",
            "always_show_filename",
        }
    )

    class Meta(SettingsBase.Meta):
        """Browser settings constraints."""

        verbose_name_plural = "browser settings"
        constraints = (
            UniqueConstraint(
                fields=("user", "client", "name"),
                condition=Q(user__isnull=False),
                name="unique_settingsbrowser_user",
            ),
            UniqueConstraint(
                fields=("session", "client", "name"),
                condition=Q(session__isnull=False),
                name="unique_settingsbrowser_session",
            ),
        )


###################
# Reader Settings #
###################

_READER_GLOBAL_SCOPE = Q(
    comic__isnull=True,
    series__isnull=True,
    folder__isnull=True,
)


class SettingsReader(SettingsBase):
    """
    Persisted reader settings.

    Scope is determined by which FK is set:
    - comic set    per-comic settings (replaces old Bookmark model)
    - series set   per-series settings (future)
    - folder set   per-folder settings (future)
    - none set     global reader defaults for the user/session
    """

    # Scope FKs — use string references to avoid circular imports.
    comic = ForeignKey(
        "codex.Comic", db_index=True, on_delete=CASCADE, null=True, blank=True
    )
    series = ForeignKey(
        "codex.Series", db_index=True, on_delete=CASCADE, null=True, blank=True
    )
    folder = ForeignKey(
        "codex.Folder", db_index=True, on_delete=SET_NULL, null=True, blank=True
    )

    # Reader display settings
    fit_to = CharField(
        blank=True,
        choices=FitToChoices.choices,
        default="",
        max_length=max_choices_len(FitToChoices),
    )
    two_pages = BooleanField(default=None, null=True)
    reading_direction = CharField(
        blank=True,
        choices=ReadingDirectionChoices.choices,
        default="",
        max_length=max_choices_len(ReadingDirectionChoices),
    )
    read_rtl_in_reverse = BooleanField(default=None, null=True)
    finish_on_last_page = BooleanField(default=None, null=True)
    page_transition = BooleanField(default=None, null=True)
    cache_book = BooleanField(default=None, null=True)

    # Dict keys that map 1:1 to a model column with the same name.
    DIRECT_KEYS = frozenset(
        {
            "fit_to",
            "two_pages",
            "reading_direction",
            "read_rtl_in_reverse",
            "finish_on_last_page",
            "page_transition",
            "cache_book",
        }
    )

    class Meta(SettingsBase.Meta):
        """Reader settings constraints."""

        verbose_name_plural = "reader settings"
        constraints = (
            # At most one scope FK may be set.
            CheckConstraint(
                condition=(
                    Q(comic__isnull=True, series__isnull=True, folder__isnull=True)
                    | Q(comic__isnull=False, series__isnull=True, folder__isnull=True)
                    | Q(comic__isnull=True, series__isnull=False, folder__isnull=True)
                    | Q(comic__isnull=True, series__isnull=True, folder__isnull=False)
                ),
                name="settingsreader_scope_xor",
            ),
            # ---- Global scope (no comic/series/folder) ----
            UniqueConstraint(
                fields=("user", "client"),
                condition=Q(user__isnull=False) & _READER_GLOBAL_SCOPE,
                name="unique_settingsreader_user_global",
            ),
            UniqueConstraint(
                fields=("session", "client"),
                condition=Q(session__isnull=False) & _READER_GLOBAL_SCOPE,
                name="unique_settingsreader_session_global",
            ),
            # ---- Comic scope ----
            UniqueConstraint(
                fields=("user", "client", "comic"),
                condition=Q(user__isnull=False, comic__isnull=False),
                name="unique_settingsreader_user_comic",
            ),
            UniqueConstraint(
                fields=("session", "client", "comic"),
                condition=Q(session__isnull=False, comic__isnull=False),
                name="unique_settingsreader_session_comic",
            ),
            # ---- Series scope ----
            UniqueConstraint(
                fields=("user", "client", "series"),
                condition=Q(user__isnull=False, series__isnull=False),
                name="unique_settingsreader_user_series",
            ),
            UniqueConstraint(
                fields=("session", "client", "series"),
                condition=Q(session__isnull=False, series__isnull=False),
                name="unique_settingsreader_session_series",
            ),
            # ---- Folder scope ----
            UniqueConstraint(
                fields=("user", "client", "folder"),
                condition=Q(user__isnull=False, folder__isnull=False),
                name="unique_settingsreader_user_folder",
            ),
            UniqueConstraint(
                fields=("session", "client", "folder"),
                condition=Q(session__isnull=False, folder__isnull=False),
                name="unique_settingsreader_session_folder",
            ),
        )
