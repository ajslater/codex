"""Codex Django Models."""
import datetime
import os

from decimal import Decimal
from logging import getLogger
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    ForeignKey,
    JSONField,
    ManyToManyField,
    Model,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextField,
    URLField,
)
from django.utils.translation import gettext_lazy as _

from codex.serializers.webpack import CHOICES


LOG = getLogger(__name__)


SCHEMA_VERSION = 1


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    # deleted_at = DateTimeField(null=True)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True


class BrowserGroupModel(BaseModel):
    """Browser groups."""

    DEFAULT_NAME = ""

    name = CharField(db_index=True, max_length=32, default=DEFAULT_NAME)
    sort_name = CharField(db_index=True, max_length=32, default=DEFAULT_NAME)

    def presave(self):
        """Save the sort name. Called by save()."""
        self.sort_name = self.name

    def save(self, *args, **kwargs):
        """Save the sort name as the name by default."""
        self.presave()
        super().save(*args, **kwargs)

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

    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta:
        """Constraints."""

        unique_together = ("name", "publisher")

    def presave(self):
        """Save the sort name. Called by save()."""
        self.sort_name = f"{self.publisher.name} {self.name}"


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

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = DecimalField(decimal_places=2, max_digits=6, null=True)

    def presave(self):
        """Save the sort name. Called by save()."""
        self.sort_name = f"{self.series.name} {self.name}"

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

    def __str__(self):
        """Return the path."""
        return self.path

    class Meta:
        """Pluralize."""

        verbose_name_plural = "libraries"


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CharField(db_index=True, max_length=32)

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
    path = CharField(max_length=128, db_index=True)
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


class Comic(WatchedPath):
    """Comic metadata."""

    # From BaseModel, but Comics are sorted by these so index them
    created_at = DateTimeField(auto_now_add=True, db_index=True)
    updated_at = DateTimeField(auto_now=True, db_index=True)

    # From WatchedPath, but interferes with related_name from folders m2m field
    parent_folder = ForeignKey(
        "Folder", on_delete=CASCADE, null=True, related_name="comic_in"
    )

    # Unique comic fields
    issue = DecimalField(
        db_index=True, decimal_places=2, max_digits=6, default=Decimal(0.0)
    )
    volume = ForeignKey(Volume, db_index=True, on_delete=CASCADE)
    series = ForeignKey(Series, db_index=True, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, db_index=True, on_delete=CASCADE)
    publisher = ForeignKey(Publisher, db_index=True, on_delete=CASCADE)
    # Date
    year = PositiveSmallIntegerField(db_index=True, null=True)
    month = PositiveSmallIntegerField(null=True)
    day = PositiveSmallIntegerField(null=True)
    # Summary
    description = TextField(null=True)
    notes = TextField(null=True)
    summary = TextField(null=True)
    # Ratings
    critical_rating = CharField(db_index=True, max_length=32, null=True)
    maturity_rating = CharField(db_index=True, max_length=32, null=True)
    user_rating = CharField(db_index=True, max_length=32, null=True)
    # alpha2 fields for countries
    country = CharField(db_index=True, max_length=32, null=True)
    language = CharField(db_index=True, max_length=16, null=True)
    # misc
    cover_image = CharField(max_length=64, null=True)
    format = CharField(db_index=True, max_length=16, null=True)
    page_count = PositiveSmallIntegerField(db_index=True, default=0)
    read_ltr = BooleanField(db_index=True, default=True)
    scan_info = CharField(max_length=32, null=True)
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
    # price = DecimalField(decimal_places=2, max_digits=9, null=True)
    # rights = CharField(max_length=64, null=True)
    # manga = BooleanField(default=False)
    # last_mark = PositiveSmallIntegerField(null=True)
    #
    # These are potentially useful, but too much work right now:
    #
    # is_version_of = CharField(max_length=64, null=True)
    # alternate_issue = DecimalField(decimal_places=2, max_digits=6, null=True)
    # alternate_volumes = ManyToManyField(Volume, related_name="alternate_volume")
    # identifier = CharField(max_length=64, null=True)

    # codex only
    cover_path = CharField(max_length=32)
    date = DateField(db_index=True, null=True)
    decade = PositiveSmallIntegerField(db_index=True, null=True)
    folders = ManyToManyField(Folder)
    max_page = PositiveSmallIntegerField(default=0)
    size = PositiveIntegerField(db_index=True)

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")
        verbose_name = "Issue"

    def _set_date(self):
        """Compute a date for the comic."""
        year = self.year if self.year is not None else datetime.MINYEAR
        month = self.month if self.month is not None else 1
        day = self.day if self.day is not None else 1
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
        sort_names = (self.volume.sort_name, f"{self.issue:06.1f}")
        self.sort_name = " ".join(sort_names)

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self.presave()
        super().save(*args, **kwargs)

    def _get_display_issue(self):
        """Get the issue number, even if its a half issue."""
        if self.issue % 1 == 0:
            issue_str = f"#{int(self.issue):0>3d}"
        else:
            issue_str = f"#{self.issue:05.1f}"
        return issue_str

    def __str__(self):
        """Most common text representation for logging."""
        names = []
        if self.series.name:
            names.append(self.series.name)
        if self.volume.name:
            names.append(self.volume.name)
        names.append(self._get_display_issue())
        if self.name:
            names.append(self.name)
        return " ".join(names)


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
    if choice is not None and choice not in CHOICES["fitTo"]:
        raise ValidationError(_(f"{choice} is not one of $(FIT_TO_CHOICE_VALUES)"))


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

    PK = 1
    version = CharField(max_length=32)

    @classmethod
    def set_version(cls, version):
        """Ensure a single database row."""
        defaults = {"version": version}
        cls.objects.update_or_create(defaults=defaults, pk=cls.PK)
