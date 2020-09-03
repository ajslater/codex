"""Codex Django Models."""
import datetime

from logging import getLogger
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db.models import CASCADE
from django.db.models import SET
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import DateField
from django.db.models import DateTimeField
from django.db.models import DecimalField
from django.db.models import DurationField
from django.db.models import ForeignKey
from django.db.models import ManyToManyField
from django.db.models import Model
from django.db.models import PositiveSmallIntegerField
from django.db.models import TextField
from django.db.models import URLField
from django.utils.translation import gettext_lazy as _

from codex.choices.static import CHOICES


LOG = getLogger(__name__)


DEFAULT_SCAN_FREQUENCY = datetime.timedelta(seconds=12 * 60 * 60)
SCHEMA_VERSION = 1


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    # deleted_at = DateTimeField(null=True)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True


class BrowseContainerModel(BaseModel):
    """Models that need parents and default to an default parent."""

    is_default = BooleanField(default=False)
    sort_name = CharField(db_index=True, max_length=32)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True


class Publisher(BrowseContainerModel):
    """The publisher of the comic."""

    DEFAULTS = {"is_default": True}
    PLURAL = "Publishers"

    name = CharField(max_length=32, default="No Publisher")

    @classmethod
    def get_default_publisher(cls):
        """Get or create a default 'No Publisher' entry."""
        publisher, _ = cls.objects.get_or_create(defaults=cls.DEFAULTS, **cls.DEFAULTS)
        return publisher

    def save(self, *args, **kwargs):
        """Save the sort name as the name by default."""
        self.sort_name = self.name
        super().save(*args, **kwargs)

    class Meta:
        """Constraints."""

        unique_together = ("name", "is_default")


class Imprint(BrowseContainerModel):
    """A Publishing imprint."""

    PLURAL = "Imprints"

    name = CharField(max_length=32, default="Main Imprint")
    publisher = ForeignKey(Publisher, on_delete=SET(Publisher.get_default_publisher))

    class Meta:
        """Contraints."""

        unique_together = ("name", "publisher", "is_default")

    def save(self, *args, **kwargs):
        """Save the sort name."""
        self.sort_name = f"{self.publisher.name} {self.name}"
        super().save(*args, **kwargs)


class Series(BrowseContainerModel):
    """The series the comic belongs to."""

    PLURAL = "Series"

    name = CharField(max_length=32, default="Default Series")
    publisher = ForeignKey(Publisher, on_delete=Publisher.get_default_publisher)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    volume_count = PositiveSmallIntegerField(null=True)

    def save(self, *args, **kwargs):
        """Save the sort name as the name by default."""
        self.sort_name = self.name
        super().save(*args, **kwargs)

    class Meta:
        """Constraints."""

        unique_together = ("name", "imprint", "is_default")


class Volume(BrowseContainerModel):
    """The volume of the series the comic belongs to."""

    PLURAL = "Volumes"

    name = CharField(max_length=32, default="")
    publisher = ForeignKey(Publisher, on_delete=Publisher.get_default_publisher)
    imprint = ForeignKey(Imprint, on_delete=CASCADE)
    series = ForeignKey(Series, on_delete=CASCADE)
    issue_count = DecimalField(decimal_places=2, max_digits=6, null=True)

    def save(self, *args, **kwargs):
        """Save the sort name."""
        self.sort_name = f"{self.series.name} {self.name}"
        super().save(*args, **kwargs)

    class Meta:
        """Constraints."""

        unique_together = ("name", "series", "is_default")


def validate_dir_exists(path):
    """Validate that a library exists."""
    if not Path(path).is_dir():
        raise ValidationError(_(f"{path} is not a directory"), params={"path": path})


class Library(BaseModel):
    """The library comic file live under."""

    path = CharField(
        unique=True, db_index=True, max_length=128, validators=[validate_dir_exists]
    )
    enable_watch = BooleanField(db_index=True, default=True)
    enable_scan_cron = BooleanField(db_index=True, default=True)
    scan_frequency = DurationField(default=DEFAULT_SCAN_FREQUENCY)
    last_scan = DateTimeField(null=True)
    scan_in_progress = BooleanField(default=False)
    schema_version = PositiveSmallIntegerField(default=0)

    def __str__(self):
        """Return the path."""
        return self.path

    class Meta:
        verbose_name_plural = "libraries"


class NamedModel(BaseModel):
    """A for simple named tables."""

    name = CharField(db_index=True, max_length=32)

    class Meta:
        """Defaults to uniquely named, must be overriden."""

        abstract = True
        unique_together = ("name",)

    def __str__(self):
        """Return the name."""
        return self.name


class Folder(NamedModel):
    """File system folder."""

    PARENT_FIELD = "folder"
    path = CharField(max_length=128, db_index=True, validators=[validate_dir_exists])
    library = ForeignKey(Library, on_delete=CASCADE)
    parent_folder = ForeignKey(
        "Folder",
        on_delete=CASCADE,
        null=True,
    )
    sort_name = CharField(max_length=32)

    def save(self, *args, **kwargs):
        """Save the sort name as the name by default."""
        self.sort_name = self.name
        super().save(*args, **kwargs)

    class Meta:
        """Constraints."""

        unique_together = ("library", "path")


Folder.CHILD_CLASS = Folder


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


class Comic(BaseModel):
    """Comic metadata."""

    PLURAL = "Issues"

    path = CharField(db_index=True, max_length=128)
    volume = ForeignKey(Volume, db_index=True, on_delete=CASCADE)
    series = ForeignKey(Series, db_index=True, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, db_index=True, on_delete=CASCADE)
    publisher = ForeignKey(Publisher, db_index=True, on_delete=CASCADE)
    issue = DecimalField(db_index=True, decimal_places=2, max_digits=6, default=0.0)
    title = CharField(db_index=True, max_length=64, null=True)
    # Date
    year = PositiveSmallIntegerField(null=True)
    month = PositiveSmallIntegerField(null=True)
    day = PositiveSmallIntegerField(null=True)
    # Summary
    summary = TextField(null=True)
    notes = TextField(null=True)
    description = TextField(null=True)
    # Ratings
    critical_rating = CharField(db_index=True, max_length=32, null=True)
    maturity_rating = CharField(db_index=True, max_length=32, null=True)
    user_rating = CharField(db_index=True, max_length=32, null=True)
    # alpha2 fields for countries
    country = CharField(db_index=True, max_length=32, null=True)
    language = CharField(db_index=True, max_length=16, null=True)
    # misc
    page_count = PositiveSmallIntegerField(db_index=True, default=0)
    cover_image = CharField(max_length=64, null=True)
    read_ltr = BooleanField(default=True)
    web = URLField(null=True)
    format = CharField(max_length=16, null=True)
    scan_info = CharField(max_length=32, null=True)
    # ManyToMany
    credits = ManyToManyField(Credit)
    tags = ManyToManyField(Tag)
    teams = ManyToManyField(Team)
    characters = ManyToManyField(Character)
    locations = ManyToManyField(Location)
    series_groups = ManyToManyField(SeriesGroup)
    story_arcs = ManyToManyField(StoryArc)
    genres = ManyToManyField(Genre)
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
    library = ForeignKey(Library, on_delete=CASCADE)
    sort_name = CharField(db_index=True, max_length=32)
    date = DateField(db_index=True, null=True)
    decade = PositiveSmallIntegerField(db_index=True, null=True)
    size = PositiveSmallIntegerField(db_index=True)
    max_page = PositiveSmallIntegerField(default=0)
    parent_folder = ForeignKey(
        Folder, db_index=True, on_delete=CASCADE, null=True, related_name="comic_in"
    )
    folder = ManyToManyField(Folder)
    cover_path = CharField(max_length=32)
    myself = ForeignKey("self", on_delete=CASCADE, null=True, related_name="comic")

    class Meta:
        """Constraints."""

        # prevents None path comics from being duplicated
        unique_together = ("path", "volume", "year", "issue")

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

    def _get_display_issue(self):
        """Get the issue number, even if its a half issue."""
        if self.issue % 1 == 0:
            issue_str = f"#{int(self.issue):0>3d}"
        else:
            issue_str = f"#{self.issue:05.1f}"
        return issue_str

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self._set_date()
        self._set_decade()
        self.sort_name = f"{self.volume.sort_name} {self.issue:06.1f}"
        super().save(*args, **kwargs)


class AdminFlag(NamedModel):
    """Flags set by administrators."""

    ENABLE_FOLDER_VIEW = "Enable Folder View"
    ENABLE_REGISTRATION = "Enable Registration"
    FLAG_NAMES = (ENABLE_FOLDER_VIEW, ENABLE_REGISTRATION)

    on = BooleanField(default=True)


def cascade_if_user_null(collector, field, sub_objs, using):
    """
    Cascade only if the user field is null.

    Do this to keep deleteing ephemeral session data from UserBookmark table.
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

    # Set them all to null, tho
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
