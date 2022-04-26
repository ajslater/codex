"""Codex Django Models."""
import calendar
import datetime
import os

from pathlib import Path
from uuid import uuid4

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
from django.utils.translation import gettext_lazy as _

from codex.serializers.choices import CHOICES
from codex.settings.logging import get_logger
from codex.settings.settings import XAPIAN_INDEX_PATH, XAPIAN_INDEX_UUID_PATH


LOG = get_logger(__name__)


SCHEMA_VERSION = 1


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    # deleted_at = DateTimeField(null=True)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True
        get_latest_by = "updated_at"


class BrowserGroupModel(BaseModel):
    """Browser groups."""

    DEFAULT_NAME = ""
    ORDERING = ("name", "pk")

    name = CharField(db_index=True, max_length=64, default=DEFAULT_NAME)

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
        unique=True, db_index=True, max_length=128, validators=[validate_dir_exists]
    )
    events = BooleanField(db_index=True, default=True)
    poll = BooleanField(db_index=True, default=True)
    poll_every = DurationField(default=DEFAULT_POLL_EVERY)
    last_poll = DateTimeField(null=True)
    update_in_progress = BooleanField(default=False)
    schema_version = PositiveSmallIntegerField(default=0)
    groups = ManyToManyField(Group, blank=True)

    def __str__(self):
        """Return the path."""
        return self.path

    class Meta:
        """Pluralize."""

        verbose_name_plural = "libraries"


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CharField(db_index=True, max_length=64)

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
    path = CharField(max_length=4095, db_index=True)
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
        # st[2] = st_record.st_dev
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
    values = Comic.FileFormats.CHOICES
    if choice not in values:
        raise ValidationError(_(f"{choice} is not one of {values}"))


class Comic(WatchedPath):
    """Comic metadata."""

    class FileFormats:
        """Identifiers for file formats."""

        COMIC = "comic"
        PDF = "pdf"
        CHOICES = frozenset((COMIC, PDF))

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
    age_rating = CharField(db_index=True, max_length=32, null=True)
    # alpha2 fields for countries
    country = CharField(db_index=True, max_length=32, null=True)
    language = CharField(db_index=True, max_length=32, null=True)
    # misc
    format = CharField(db_index=True, max_length=16, null=True)
    page_count = PositiveSmallIntegerField(db_index=True, default=0)
    read_ltr = BooleanField(db_index=True, default=True)
    scan_info = CharField(max_length=128, null=True)
    web = URLField(null=True)
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
    #
    # black_and_white = BooleanField(default=False)
    # last_mark = PositiveSmallIntegerField(null=True)
    # manga = BooleanField(default=False)
    # price = DecimalField(decimal_places=2, max_digits=9, null=True)
    # rights = CharField(max_length=64, null=True)
    #
    # These are potentially useful, but too much work right now:
    #
    # alternate_issue = DecimalField(decimal_places=2, max_digits=6, null=True)
    # alternate_volumes = ManyToManyField(Volume, related_name="alternate_volume")
    # cover_image = CharField(max_length=256, null=True)
    # identifier = CharField(max_length=64, null=True)
    # is_version_of = CharField(max_length=64, null=True)

    # codex only
    cover_path = CharField(max_length=4095)
    date = DateField(db_index=True, null=True)
    decade = PositiveSmallIntegerField(db_index=True, null=True)
    folders = ManyToManyField(Folder)
    max_page = PositiveSmallIntegerField(default=0)
    size = PositiveIntegerField(db_index=True)
    file_format = CharField(
        validators=[validate_file_format_choice], max_length=5, default="comic"
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
    FLAG_NAMES = (
        ENABLE_FOLDER_VIEW,
        ENABLE_REGISTRATION,
        ENABLE_NON_USERS,
        ENABLE_AUTO_UPDATE,
    )
    DEFAULT_FALSE = (ENABLE_AUTO_UPDATE,)

    on = BooleanField(default=True)


def cascade_if_user_null(collector, field, sub_objs, _using):
    """
    Cascade only if the user field is null.

    Do this to keep deleting ephemeral session data from UserBookmark table.
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
            # fail_on_restricted=False,
        )

    # Set them all to null
    if field.null:
        # and not connections[using].features.can_defer_constraint_checks:
        collector.add_field_update(field, None, sub_objs)


def validate_fit_to_choice(choice):
    """Validate fit to choice."""
    values = CHOICES["fitTo"]
    if choice is not None and choice not in values:
        raise ValidationError(_(f"{choice} is not one of {values}"))


class UserBookmark(BaseModel):
    """Persist user's bookmarks and settings."""

    user = ForeignKey(
        settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE, null=True
    )
    session = ForeignKey(
        Session, db_index=True, on_delete=cascade_if_user_null, null=True
    )
    comic = ForeignKey(Comic, db_index=True, on_delete=CASCADE)
    bookmark = PositiveSmallIntegerField(db_index=True, null=True)
    finished = BooleanField(default=False, db_index=True)
    fit_to = CharField(
        validators=[validate_fit_to_choice], null=True, default=None, max_length=6
    )
    two_pages = BooleanField(default=None, null=True)

    class Meta:
        """Constraints."""

        unique_together = ("user", "session", "comic")


class FailedImport(WatchedPath):
    """Failed Comic Imports. Displayed in Admin Panel."""

    MAX_REASON_LEN = 32

    def set_reason(self, exc):
        """Can't do this in save() because it breaks update_or_create."""
        reason = str(exc)
        suffixes = (f": {self.path}", f": '{self.path}'")
        for suffix in suffixes:
            reason = reason.removesuffix(suffix)
        reason = reason[: self.MAX_REASON_LEN]
        self.name = reason.strip()

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")


class LatestVersion(BaseModel):
    """Latest codex version."""

    CODEX_VERSION_PK = 1
    XAPIAN_INDEX_VERSION_PK = 2
    version = CharField(max_length=32)

    @classmethod
    def _update_or_create(cls, pk, version):
        search_kwargs = {"pk": pk}
        defaults = {"version": version}
        cls.objects.update_or_create(defaults=defaults, **search_kwargs)

    @classmethod
    def set_codex_version(cls, version):
        """Ensure a single database row."""
        cls._update_or_create(cls.CODEX_VERSION_PK, version)

    @classmethod
    def set_xapian_index_version(cls):
        """Set the codex db to xapian matching id."""
        version = str(uuid4())
        try:
            cls._update_or_create(cls.XAPIAN_INDEX_VERSION_PK, version)
            XAPIAN_INDEX_PATH.mkdir(parents=True, exist_ok=True)
            with XAPIAN_INDEX_UUID_PATH.open("w") as uuid_file:
                uuid_file.write(version)
        except Exception as exc:
            LOG.error(f"Setting search index to db synchronization token: {exc}")

    @classmethod
    def is_xapian_uuid_match(cls):
        """Is this xapian index for this database."""
        result = False
        try:
            with XAPIAN_INDEX_UUID_PATH.open("r") as uuid_file:
                version = uuid_file.read()
            lv = cls.objects.only("pk").get(
                pk=cls.XAPIAN_INDEX_VERSION_PK, version=version
            )
            result = lv.pk == cls.XAPIAN_INDEX_VERSION_PK
        except (FileNotFoundError, cls.DoesNotExist):
            pass
        except Exception as exc:
            LOG.exception(exc)
        return result


class SearchQuery(Model):
    """Search queries."""

    text = CharField(db_index=True, unique=True, max_length=256)
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
