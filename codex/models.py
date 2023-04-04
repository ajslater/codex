"""Codex Django Models."""
import base64
import calendar
import datetime
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    Choices,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    ForeignKey,
    JSONField,
    ManyToManyField,
    Model,
    OneToOneField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextChoices,
    TextField,
    URLField,
)
from django.utils.translation import gettext_lazy as _

from codex.librarian.covers.status import CoverStatusTypes
from codex.librarian.importer.status import ImportStatusTypes
from codex.librarian.janitor.status import JanitorStatusTypes
from codex.librarian.search.status import SearchIndexStatusTypes
from codex.librarian.watchdog.status import WatchdogStatusTypes
from codex.logger.logging import get_logger

LOG = get_logger(__name__)


MAX_PATH_LEN = 4095
MAX_NAME_LEN = 128
MAX_FIELD_LEN = 32


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

    name = CharField(db_index=True, max_length=MAX_NAME_LEN, default=DEFAULT_NAME)

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
    YEAR_LEN = 4

    publisher = ForeignKey(Publisher, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = PositiveSmallIntegerField(null=True)

    class Meta:
        """Constraints."""

        unique_together = ("name", "series")

    @classmethod
    def to_str(cls, name):
        """Represent volume as a string."""
        if not name:
            vol = ""
        elif len(name) == cls.YEAR_LEN:
            vol = f"({name})"
        else:
            vol = "v" + name
        return vol

    def __str__(self):
        """Represent volume as a string."""
        return self.to_str(self.name)


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
        max_length=MAX_PATH_LEN,
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

        verbose_name_plural = "Libraries"


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CharField(db_index=True, max_length=MAX_NAME_LEN)

    class Meta:
        """Defaults to uniquely named, must be overridden."""

        abstract = True
        unique_together = ("name",)

    def __str__(self):
        """Return the name."""
        return self.name


class SeriesGroup(NamedModel):
    """A series group the series is part of."""


class StoryArc(NamedModel):
    """A story arc the comic is part of."""


class Location(NamedModel):
    """A location that appears in the comic."""


class Character(NamedModel):
    """A character that appears in the comic."""


class Team(NamedModel):
    """A team that appears in the comic."""


class Tag(NamedModel):
    """Arbitrary Metadata Tag."""


class Genre(NamedModel):
    """The genre the comic belongs to."""


class CreatorPerson(NamedModel):
    """Credited persons."""


class CreatorRole(NamedModel):
    """A role for the credited person. Writer, Inker, etc."""


class Creator(BaseModel):
    """A creator credit."""

    person = ForeignKey(CreatorPerson, on_delete=CASCADE)
    role = ForeignKey(CreatorRole, on_delete=CASCADE, null=True)

    class Meta:
        """Constraints."""

        unique_together = ("person", "role")


class WatchedPath(BrowserGroupModel):
    """A filesystem path with data for Watchdog."""

    library = ForeignKey(Library, on_delete=CASCADE, db_index=True)
    path = CharField(max_length=MAX_PATH_LEN, db_index=True)
    stat = JSONField(null=True)
    parent_folder = ForeignKey(
        "Folder",
        on_delete=CASCADE,
        null=True,
    )
    ZERO_STAT = [0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0]

    def set_stat(self):
        """Set select stat params from the filesystem."""
        st_record = Path(self.path).stat()
        # Converting os.stat directly to a list or tuple saves
        # mtime as an int and causes problems.
        st = self.ZERO_STAT.copy()
        st[0] = st_record.st_mode
        st[1] = st_record.st_ino
        # st[2] = st_record.st_dev is ignored by diff
        # st[3] = st_record.st_nlink
        # st[4] = st_record.st_uid
        # st[5] = st_record.st_gid
        st[6] = st_record.st_size
        # st[7] = st_record.st_atime
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

    class FileType(Choices):
        """Identifiers for file formats."""

        CBZ = "CBZ"
        CBR = "CBR"
        CBT = "CBT"
        PDF = "PDF"

    ORDERING = ("series__name", "volume__name", "issue", "issue_suffix", "name", "pk")
    _RE_COMBINE_WHITESPACE = re.compile(r"\s+")

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
    comments = TextField(default="")
    notes = TextField(default="")
    summary = TextField(default="")
    # Ratings
    community_rating = DecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )
    critical_rating = DecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )
    age_rating = CharField(db_index=True, max_length=MAX_FIELD_LEN, default="")
    # alpha2 fields for countries
    country = CharField(db_index=True, max_length=MAX_FIELD_LEN, default="")
    language = CharField(db_index=True, max_length=MAX_FIELD_LEN, default="")
    # misc
    original_format = CharField(db_index=True, max_length=MAX_FIELD_LEN, default="")
    page_count = PositiveSmallIntegerField(db_index=True, default=0)
    read_ltr = BooleanField(db_index=True, default=True)
    scan_info = CharField(max_length=MAX_NAME_LEN, default="")
    web = URLField(default="")
    # ManyToMany
    characters = ManyToManyField(Character)
    creators = ManyToManyField(Creator)
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
    file_type = CharField(
        choices=FileType.choices,
        max_length=3,
        blank=True,
        default="",
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
        month = 1 if self.month is None else min(max(self.month, 1), 12)

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

    @classmethod
    def get_filename(cls, obj, ext=True):
        """Get the fileaname from dict."""
        names = []
        if sn := obj.get("series_name"):
            names.append(sn)
        if vn := obj.get("volume_name"):
            vn = Volume.to_str(vn)
            names.append(vn)
        issue = obj.get("issue")
        if issue is not None:
            issue_str = "#"
            if issue % 1 == 0:
                issue_str += f"{issue:05.0f}"
            else:
                issue_str += f"{issue:06.1f}"
            if issue_suffix := obj.get("issue_suffix"):
                issue_str += issue_suffix
            names.append(issue_str)
        if name := obj.get("name"):
            names.append(name)

        fn = " ".join(names).strip(" .")
        fn = cls._RE_COMBINE_WHITESPACE.sub(" ", fn).strip()
        if ext:
            ft = obj.get("file_type", "cbz")
            fn += "." + ft.lower()
        return fn

    def filename(self, ext=True):
        """Create a filename for download."""
        obj = {
            "series_name": self.series.name,
            "volume_name": self.volume.name,
            "issue": self.issue,
            "issue_suffix": self.issue_suffix,
        }
        if ext:
            obj["file_type"] = self.file_type
        return self.get_filename(obj, ext=ext)

    def __str__(self):
        """Most common text representation for logging."""
        return self.filename(ext=False)


class AdminFlag(BaseModel):
    """Flags set by administrators."""

    class FlagChoices(Choices):
        """Choices for Admin Flags."""

        FOLDER_VIEW = "FV"
        REGISTRATION = "RG"
        NON_USERS = "NU"
        AUTO_UPDATE = "AU"
        SEARCH_INDEX_OPTIMIZE = "SO"

    FALSE_DEFAULTS = frozenset((FlagChoices.AUTO_UPDATE,))

    key = CharField(db_index=True, max_length=2, choices=FlagChoices.choices)
    on = BooleanField(default=True)

    class Meta:
        """Constraints."""

        unique_together = ("key",)


def cascade_if_user_null(collector, field, sub_objs, _using):
    """Cascade only if the user field is null.

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


class Bookmark(BaseModel):
    """Persist user's bookmarks and settings."""

    class FitTo(Choices):
        """Identifiers for Readder fit_to choices."""

        SCREEN = "S"
        WIDTH = "W"
        HEIGHT = "H"
        ORIG = "O"

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
        choices=FitTo.choices,
        blank=True,
        default="",
        max_length=1,
    )
    two_pages = BooleanField(default=None, null=True)
    read_in_reverse = BooleanField(default=None, null=True)
    vertical = BooleanField(default=None, null=True)

    class Meta:
        """Constraints."""

        unique_together = ("user", "session", "comic")


class FailedImport(WatchedPath):
    """Failed Comic Imports. Displayed in Admin Panel."""

    def set_reason(self, exc):
        """Can't do this in save() because it breaks update_or_create."""
        reason = str(exc)
        suffixes = (f": {self.path}", f": {self.path!r}")
        for suffix in suffixes:
            reason = reason.removesuffix(suffix)
        reason = reason[:MAX_NAME_LEN]
        self.name = reason.strip()

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")


class LibrarianStatus(BaseModel):
    """Active Library Tasks."""

    CHOICES = (
        CoverStatusTypes.choices
        + ImportStatusTypes.choices
        + JanitorStatusTypes.choices
        + SearchIndexStatusTypes.choices
        + WatchdogStatusTypes.choices
    )

    status_type = CharField(db_index=True, max_length=3, choices=CHOICES)
    preactive = BooleanField(default=False)
    complete = PositiveSmallIntegerField(null=True, default=None)
    total = PositiveSmallIntegerField(null=True, default=None)
    active = DateTimeField(null=True, default=None)
    subtitle = CharField(db_index=True, max_length=MAX_NAME_LEN)

    class Meta:
        """Constraints."""

        unique_together = ("status_type", "subtitle")
        verbose_name_plural = "LibrarianStatuses"


class Timestamp(BaseModel):
    """Timestamped Named Strings."""

    class TimestampChoices(TextChoices):
        """Choices for Timestamps."""

        COVERS = "CV", _("Covers")
        JANITOR = "JA", _("Janitor")
        CODEX_VERSION = "VR", _("Codex Version")
        SEARCH_INDEX_UUID = "SI", _("Search Index UUID")
        API_KEY = "AP", _("API Key")

    key = CharField(db_index=True, max_length=2, choices=TimestampChoices.choices)
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

    class Meta:
        """Constraints."""

        unique_together = ("key",)

    def __str__(self):
        """Print name for choice."""
        return self.TimestampChoices(self.key).name


class UserActive(BaseModel):
    """User last active record."""

    user = OneToOneField(settings.AUTH_USER_MODEL, db_index=True, on_delete=CASCADE)
