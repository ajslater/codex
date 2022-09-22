"""Codex Django Models."""
import calendar
import datetime
import os

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    ForeignKey,
    Index,
    JSONField,
    ManyToManyField,
    Model,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextField,
    URLField,
)
from django.db.models.enums import TextChoices
from django.utils.translation import gettext_lazy as _

from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.db.status import ImportStatusTypes
from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.watchdog.status import WatchdogStatusTypes
from codex.serializers.choices import CHOICES
from codex.settings.logging import get_logger


LOG = get_logger(__name__)


MAX_PATH_LENGTH = 4095
MAX_NAME_LENGTH = 128


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True
        get_latest_by = "updated_at"


class BrowserGroupModel(BaseModel):
    """Browser groups."""

    DEFAULT_NAME = ""
    ORDERING = ("name", "pk")

    name = CharField(db_index=True, max_length=MAX_NAME_LENGTH, default=DEFAULT_NAME)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True


class Publisher(BrowserGroupModel):
    """The publisher of the comic."""

    class Meta:
        """Constraints."""

        unique_together = ("name",)


class Imprint(BrowserGroupModel):
    """A Publishing imprint."""

    ORDERING = ("publisher__name", "name", "pk")

    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta:
        """Constraints."""

        unique_together = ("name", "publisher")


class Series(BrowserGroupModel):
    """The series the comic belongs to."""

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    volume_count = PositiveSmallIntegerField(null=True)

    class Meta:
        """Constraints."""

        unique_together = ("name", "imprint")
        verbose_name_plural = "Series"


class Volume(BrowserGroupModel):
    """The volume of the series the comic belongs to."""

    ORDERING = ("series__name", "name", "pk")

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = PositiveSmallIntegerField(null=True)

    class Meta:
        """Constraints."""

        unique_together = ("name", "series")


def validate_dir_exists(path):
    """Validate that a library exists."""
    if not Path(path).is_dir():
        raise ValidationError(_(f"{path} is not a directory"), params={"path": path})


class Library(BaseModel):
    """The library comic file live under."""

    DEFAULT_POLL_EVERY_SECONDS = 60 * 60
    DEFAULT_POLL_EVERY = datetime.timedelta(seconds=DEFAULT_POLL_EVERY_SECONDS)

    path = CharField(
        unique=True,
        db_index=True,
        max_length=MAX_PATH_LENGTH,
        validators=[validate_dir_exists],
    )
    events = BooleanField(db_index=True, default=True)
    poll = BooleanField(db_index=True, default=True)
    poll_every = DurationField(default=DEFAULT_POLL_EVERY)
    last_poll = DateTimeField(null=True)
    update_in_progress = BooleanField(default=False)
    groups = ManyToManyField(Group, blank=True)

    def __str__(self):
        """Return the path."""
        return self.path

    class Meta:
        """Pluralize."""

        verbose_name_plural = "libraries"


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CharField(db_index=True, max_length=MAX_NAME_LENGTH)

    class Meta:
        """Defaults to uniquely named, must be overridden."""

        abstract = True
        unique_together = ("name",)

    def __str__(self):
        """Return the name."""
        return self.name


class SeriesGroup(NamedModel):
    """A series group the series is part of."""

    pass


class StoryArc(NamedModel):
    """A story arc the comic is part of."""

    pass


class Location(NamedModel):
    """A location that appears in the comic."""


class Character(NamedModel):
    """A character that appears in the comic."""

    pass


class Team(NamedModel):
    """A team that appears in the comic."""

    pass


class Tag(NamedModel):
    """Arbitrary Metadata Tag."""

    pass


class Genre(NamedModel):
    """The genre the comic belongs to."""

    pass


class CreditPerson(NamedModel):
    """Credited persons."""

    pass


class CreditRole(NamedModel):
    """A role for the credited person. Writer, Inker, etc."""

    pass


class Credit(BaseModel):
    """A creator credit."""

    person = ForeignKey(CreditPerson, on_delete=CASCADE)
    role = ForeignKey(CreditRole, on_delete=CASCADE, null=True)

    class Meta:
        """Constraints."""

        unique_together = ("person", "role")


class WatchedPath(BrowserGroupModel):
    """A filesystem path with data for Watchdog."""

    library = ForeignKey(Library, on_delete=CASCADE, db_index=True)
    path = CharField(max_length=MAX_PATH_LENGTH, db_index=True)
    stat = JSONField(null=True)
    parent_folder = ForeignKey(
        "Folder",
        on_delete=CASCADE,
        null=True,
    )
    ZERO_STAT = [0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0]

    def set_stat(self):
        """Set select stat params from the filesystem."""
        st_record = os.stat(self.path)
        # Converting os.stat directly to a list or tuple saves
        # mtime as an int and causes problems.
        st = self.ZERO_STAT.copy()
        st[0] = st_record.st_mode
        st[1] = st_record.st_ino
        # st_dev changes every time with docker
        st[6] = st_record.st_size
        st[8] = st_record.st_mtime
        self.stat = st

    def __str__(self):
        """Return the full path."""
        return self.path

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")
        abstract = True


class Folder(WatchedPath):
    """File system folder."""


def validate_file_format_choice(choice):
    """Validate file format."""
    values = Comic.FileFormat.values
    if choice not in values:
        raise ValidationError(_(f"{choice} is not one of {values}"))


class Comic(WatchedPath):
    """Comic metadata."""

    class FileFormat(TextChoices):
        """Identifiers for file formats."""

        COMIC = "comic"
        PDF = "pdf"

    ORDERING = ("series__name", "volume__name", "issue", "issue_suffix", "name", "pk")

    # From BaseModel, but Comics are sorted by these so index them
    created_at = DateTimeField(auto_now_add=True, db_index=True)
    updated_at = DateTimeField(auto_now=True, db_index=True)

    # From WatchedPath, but interferes with related_name from folders m2m field
    parent_folder = ForeignKey(
        "Folder", on_delete=CASCADE, null=True, related_name="comic_in"
    )

    # Unique comic fields
    issue = DecimalField(db_index=True, decimal_places=2, max_digits=10, null=True)
    issue_suffix = CharField(db_index=True, max_length=16, default="")
    volume = ForeignKey(Volume, db_index=True, on_delete=CASCADE)
    series = ForeignKey(Series, db_index=True, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, db_index=True, on_delete=CASCADE)
    publisher = ForeignKey(Publisher, db_index=True, on_delete=CASCADE)
    # Date
    year = PositiveSmallIntegerField(db_index=True, null=True)
    month = PositiveSmallIntegerField(null=True)
    day = PositiveSmallIntegerField(null=True)
    # Summary
    comments = TextField(null=True)
    notes = TextField(null=True)
    summary = TextField(null=True)
    # Ratings
    community_rating = DecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )
    critical_rating = DecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )
    age_rating = CharField(db_index=True, max_length=32, default="")
    # alpha2 fields for countries
    country = CharField(db_index=True, max_length=32, default="")
    language = CharField(db_index=True, max_length=32, default="")
    # misc
    format = CharField(db_index=True, max_length=32, default="")
    page_count = PositiveSmallIntegerField(db_index=True, default=0)
    read_ltr = BooleanField(db_index=True, default=True)
    scan_info = CharField(max_length=MAX_NAME_LENGTH, default="")
    web = URLField(default="")
    # ManyToMany
    characters = ManyToManyField(Character)
    credits = ManyToManyField(Credit)
    genres = ManyToManyField(Genre)
    locations = ManyToManyField(Location)
    series_groups = ManyToManyField(SeriesGroup)
    story_arcs = ManyToManyField(StoryArc)
    tags = ManyToManyField(Tag)
    teams = ManyToManyField(Team)
    # Ignore these, they seem useless:
    # black_and_white
    # last_mark
    # manga
    # price
    # rights
    #
    # These are potentially useful, but too much work right now:
    # alternate_issue
    # alternate_volumes
    # cover_image
    # identifier
    # is_version_of

    # codex only
    date = DateField(db_index=True, null=True)
    decade = PositiveSmallIntegerField(db_index=True, null=True)
    folders = ManyToManyField(Folder)
    max_page = PositiveSmallIntegerField(default=0)
    size = PositiveIntegerField(db_index=True)
    file_format = CharField(
        choices=FileFormat.choices,
        max_length=max((len(val) for val in FileFormat.values)),
        default=FileFormat.COMIC.value,
    )

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")
        verbose_name = "Issue"

    def _set_date(self):
        """Compute a date for the comic."""
        if self.year is None:
            year = datetime.MINYEAR
        else:
            year = min(max(self.year, datetime.MINYEAR), datetime.MAXYEAR)
        if self.month is None:
            month = 1
        else:
            month = min(max(self.month, 1), 12)

        if self.day is None:
            day = 1
        else:
            last_day_of_month = calendar.monthrange(year, month)[1]
            day = min(max(self.day, 1), last_day_of_month)

        self.date = datetime.date(year, month, day)

    def _set_decade(self):
        """Compute a decade for the comic."""
        if self.year is None:
            self.decade = None
        else:
            self.decade = self.year - (self.year % 10)

    def presave(self):
        """Set computed values."""
        self._set_date()
        self._set_decade()
        self.max_page = max(self.page_count - 1, 0)
        self.size = Path(self.path).stat().st_size

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self.presave()
        super().save(*args, **kwargs)

    def __str__(self):
        """Most common text representation for logging."""
        names = []
        if self.series.name:
            names.append(self.series.name)
        if self.volume.name:
            names.append(self.volume.name)
        if self.issue is not None:
            names.append(f"#{self.issue:06.1f}")
        if self.issue_suffix:
            names.append(self.issue_suffix)
        if self.name:
            names.append(self.name)
        return " ".join(names).strip()


class AdminFlag(NamedModel):
    """Flags set by administrators."""

    ENABLE_FOLDER_VIEW = "Enable Folder View"
    ENABLE_REGISTRATION = "Enable Registration"
    ENABLE_NON_USERS = "Enable Non Users"
    ENABLE_AUTO_UPDATE = "Enable Auto Update"
    FLAG_NAMES = {
        ENABLE_FOLDER_VIEW: True,
        ENABLE_REGISTRATION: True,
        ENABLE_NON_USERS: True,
        ENABLE_AUTO_UPDATE: False,
    }

    on = BooleanField(default=True)


def cascade_if_user_null(collector, field, sub_objs, _using):
    """
    Cascade only if the user field is null.

    Do this to keep deleting ephemeral session data from Bookmark table.
    Adapted from:
    https://github.com/django/django/blob/master/django/db/models/deletion.py#L23
    """
    null_user_sub_objs = []
    for sub_obj in sub_objs:
        # only cascade the ones with null user fields.
        if sub_obj.user is None:
            null_user_sub_objs.append(sub_obj)

    if null_user_sub_objs:
        collector.collect(
            null_user_sub_objs,
            source=field.remote_field.model,
            source_attr=field.name,
            nullable=field.null,
        )

    # Set them all to null
    if field.null:
        # and not connections[using].features.can_defer_constraint_checks:
        collector.add_field_update(field, None, sub_objs)


def validate_fit_to_choice(choice):
    """Validate fit to choice."""
    # Choices is loaded after migration time and after definition time.
    values = frozenset((None, *CHOICES["fitTo"]))
    if choice not in values:
        raise ValidationError(_(f"{choice} is not one of {values}"))


class Bookmark(BaseModel):
    """Persist user's bookmarks and settings."""

    user = ForeignKey(
        settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE, null=True
    )
    session = ForeignKey(
        Session, db_index=True, on_delete=cascade_if_user_null, null=True
    )
    comic = ForeignKey(Comic, db_index=True, on_delete=CASCADE)
    page = PositiveSmallIntegerField(db_index=True, null=True)
    finished = BooleanField(default=False, db_index=True)
    fit_to = CharField(
        validators=[validate_fit_to_choice],
        default="",
        blank=True,
        max_length=len("SCREEN"),
    )
    two_pages = BooleanField(default=None, null=True)

    class Meta:
        """Constraints."""

        unique_together = ("user", "session", "comic")


class FailedImport(WatchedPath):
    """Failed Comic Imports. Displayed in Admin Panel."""

    def set_reason(self, exc):
        """Can't do this in save() because it breaks update_or_create."""
        reason = str(exc)
        suffixes = (f": {self.path}", f": '{self.path}'")
        for suffix in suffixes:
            reason = reason.removesuffix(suffix)
        reason = reason[:MAX_NAME_LENGTH]
        self.name = reason.strip()

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")


class SearchQuery(Model):
    """Search queries."""

    QUERY_MAX_LENGTH = 256

    text = CharField(db_index=True, unique=True, max_length=QUERY_MAX_LENGTH)
    used_at = DateTimeField(auto_now_add=True, db_index=True)


class SearchResult(Model):
    """results model."""

    query = ForeignKey(SearchQuery, on_delete=CASCADE)
    comic = ForeignKey(Comic, on_delete=CASCADE)
    score = PositiveSmallIntegerField()

    @classmethod
    def truncate_and_reset(cls):
        """Nuke this table and reset the autoincrementer."""
        cls.objects.all().delete()
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sqlite_sequence SET seq=1 WHERE name=%s", [cls._meta.db_table]
            )

    class Meta:
        """These are usually looked up by comic & autoquery hash."""

        unique_together = ("query", "comic")
        indexes = [Index(fields=["comic", "query"])]


class LibrarianStatus(NamedModel):
    """Active Library Tasks."""

    DEFAULT_PARAMS = {
        "name": "",
        "preactive": False,
        "complete": 0,
        "total": 0,
        "active": None,
    }
    TYPES = (
        *CoverStatusTypes.values(),
        *ImportStatusTypes.values(),
        *JanitorStatusTypes.values(),
        *SearchIndexStatusTypes.values(),
        *WatchdogStatusTypes.values(),
    )
    type = CharField(db_index=True, max_length=32)
    preactive = BooleanField(default=False)
    complete = PositiveSmallIntegerField(default=0)
    total = PositiveSmallIntegerField(default=0)
    active = DateTimeField(null=True, default=None)

    class Meta:
        """Constraints."""

        unique_together = ("type", "name")


class Timestamp(NamedModel):
    """Timestamp."""

    COVERS = "covers"
    JANITOR = "janitor"
    SEARCH_INDEX = "search_index"
    CODEX_VERSION = "codex_version"
    XAPIAN_INDEX_UUID = "xapian_index_uuid"
    NAMES = (COVERS, JANITOR, SEARCH_INDEX, CODEX_VERSION, XAPIAN_INDEX_UUID)

    version = CharField(max_length=32, default="")

    @classmethod
    def touch(cls, name):
        """Touch a timestamp."""
        cls.objects.get(name=name).save()

    @classmethod
    def get(cls, name):
        """Get the timestamp."""
        return cls.objects.get(name=name).updated_at.timestamp()
