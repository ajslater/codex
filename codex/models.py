"""Codex Django Models."""

import datetime

from django.db.models import PROTECT
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
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .validators import validate_path_exists


DEFAULT_SCAN_FREQUENCY = datetime.timedelta(seconds=12 * 60 * 60)


class BaseModel(Model):
    """A base model with universal fields."""

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    deleted_at = DateTimeField(null=True)

    def soft_delete(self):
        """Mark deleted."""
        self.deleted_at = timezone.now()

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True


class NamedModel(BaseModel):
    """A base model with universal fields."""

    name = CharField(max_length=32)

    class Meta:
        """Defaults to uniquely named, must be overriden."""

        abstract = True
        unique_together = ["name"]


class DisplayNamedModel(NamedModel):
    """Models that have special displayed names."""

    display_name = CharField(max_length=32)

    def _set_display_name(self):
        """Use the short name for display."""
        self.display_name = self.name

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self._set_display_name()
        super().save(*args, **kwargs)

    class Meta:
        """Defaults to uniquely named, must be overriden."""

        abstract = True
        unique_together = ["name"]


class ParentMixin:
    """Default properties for catalogue classes with parents."""

    PARENT_CLS = None
    PARENT_FIELD = None

    @property
    def parent(self):
        """Alias."""
        return getattr(self, self.PARENT_FIELD)


class CatalogueGroupModel(DisplayNamedModel, ParentMixin):
    """Models that need parents and default to an default parent."""

    BROWSE_TYPE = "Browse"
    is_default = BooleanField(default=False)

    class Meta:
        """Without this a real table is created and joined to."""

        abstract = True

    def _set_display_name(self):
        """Use the short name for display."""
        self.display_name = self.name

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self._set_display_name()
        super().save(*args, **kwargs)


class Publisher(CatalogueGroupModel):
    """The publisher of the comic."""

    COMIC_RELATION = "imprint__series__volume__comic__"
    DEFAULT_NAME = "No Publisher"
    DEFAULTS = {"name": DEFAULT_NAME, "is_default": True}
    parent = None
    PLURAL = _("Publishers")

    @classmethod
    def get_default_publisher(cls):
        """Get or create an 'no publisher' entry."""
        publisher, _ = cls.objects.get_or_create(defaults=cls.DEFAULTS, **cls.DEFAULTS)
        return publisher

    class Meta:
        """Constraints."""

        unique_together = ["name", "is_default"]


class Imprint(CatalogueGroupModel):
    """A Publishing imprint."""

    COMIC_RELATION = "series__volume__comic__"
    PARENT_CLS = Publisher
    PARENT_FIELD = PARENT_CLS.__name__.lower()
    DEFAULT_NAME = "Main Imprint"
    PLURAL = _("Imprints")

    publisher = ForeignKey(Publisher, on_delete=SET(Publisher.get_default_publisher))

    def _set_display_name(self):
        """Set long display name for disambiguation."""
        name = self.name if self.name else self.DEFAULT_NAME
        self.display_name = " ".join((self.parent.name, name))

    class Meta:
        """Without this a real table is created and joined to."""

        unique_together = ["name", "publisher", "is_default"]


class Series(CatalogueGroupModel):
    """The series the comic belongs to."""

    COMIC_RELATION = "volume__comic__"
    PARENT_CLS = Imprint
    PARENT_FIELD = PARENT_CLS.__name__.lower()
    DEFAULT_NAME = "Default Series"
    PLURAL = _("Series")

    imprint = ForeignKey(Imprint, on_delete=PROTECT)
    volume_count = PositiveSmallIntegerField(null=True)

    class Meta:
        """Without this a real table is created and joined to."""

        unique_together = ["name", "imprint", "is_default"]


class Volume(CatalogueGroupModel):
    """The volume of the series the comic belongs to."""

    COMIC_RELATION = "comic__"
    PARENT_CLS = Series
    PARENT_FIELD = PARENT_CLS.__name__.lower()
    DEFAULT_NAME = "0"
    PLURAL = _("Volumes")

    series = ForeignKey(Series, on_delete=PROTECT)
    issue_count = DecimalField(decimal_places=2, max_digits=6, null=True)

    def _set_display_name(self):
        """Set long display name for disambiguation."""
        name = self.name if self.name else self.DEFAULT_NAME
        display_name = None
        try:
            if len(f"{name:d}") == 4:
                display_name = f"({name})"
        except ValueError:
            pass
        if display_name is None:
            display_name = f"v{name}"

        self.display_name = " ".join((self.parent.name, display_name))

    class Meta:
        """Without this a real table is created and joined to."""

        unique_together = ["name", "series", "is_default"]


class RootPath(BaseModel):
    """The root path the comic file live under."""

    path = CharField(unique=True, max_length=128, validators=[validate_path_exists])
    scan_frequency = DurationField(default=DEFAULT_SCAN_FREQUENCY)
    last_scan = DateTimeField(null=True)


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

    person = ForeignKey(CreditPerson, on_delete=PROTECT)
    role = ForeignKey(CreditRole, on_delete=PROTECT)

    class Meta:
        """Constraints."""

        unique_together = ["person", "role"]


class Comic(DisplayNamedModel, ParentMixin):
    """Comic metadata."""

    COMIC_RELATION = ""
    PARENT_CLS = Volume
    PARENT_FIELD = PARENT_CLS.__name__.lower()
    BROWSE_TYPE = "Comic"
    RELATIONS = {
        Publisher: "volume__series__imprint__publisher",
        Imprint: "volume__series__imprint",
        Series: "volume__series",
        Volume: "volume",
    }
    DATE_ORDER = ("year", "month", "day")
    ALPHA_ORDER = ("volume__series__name", "volume__name", "issue")
    PLURAL = _("Issues")

    path = CharField(max_length=128, null=True)
    volume = ForeignKey(Volume, on_delete=PROTECT)
    issue = DecimalField(decimal_places=2, max_digits=6, default=0.0)
    alternate_issue = DecimalField(decimal_places=2, max_digits=6, null=True)
    title = CharField(max_length=64, null=True)
    # date
    year = PositiveSmallIntegerField(null=True)
    month = PositiveSmallIntegerField(null=True)
    day = PositiveSmallIntegerField(null=True)
    # Free text fields
    comments = TextField(null=True)
    notes = TextField(null=True)
    description = TextField(null=True)
    # Ratings
    critical_rating = CharField(max_length=32, null=True)
    maturity_rating = CharField(max_length=32, null=True)
    user_rating = CharField(max_length=32, null=True)
    # alpha2 fields for countries
    country = CharField(max_length=2, null=True)
    language = CharField(max_length=2, null=True)
    # misc
    web = URLField(null=True)
    book_format = CharField(max_length=16, null=True)
    read_ltr = BooleanField(default=True)
    page_count = PositiveSmallIntegerField(default=0)
    cover_image = CharField(max_length=64, null=True)
    scan_info = CharField(max_length=32, null=True)
    black_and_white = BooleanField(default=False)
    identifier = CharField(max_length=64, null=True)
    # ManyToMany
    credits = ManyToManyField(Credit)
    tags = ManyToManyField(Tag)
    teams = ManyToManyField(Team)
    characters = ManyToManyField(Character)
    locations = ManyToManyField(Location)
    alternate_volumes = ManyToManyField(Volume, related_name="alternate_volume")
    series_groups = ManyToManyField(SeriesGroup)
    story_arcs = ManyToManyField(StoryArc)
    genres = ManyToManyField(Genre)
    # Ignore these
    # price = DecimalField(decimal_places=2, max_digits=9, null=True)
    # is_version_of = CharField(max_length=64, null=True)
    # rights = CharField(max_length=64, null=True)
    # manga = BooleanField(default=False)
    # last_mark = PositiveSmallIntegerField(null=True)

    # codex only
    root_path = ForeignKey(RootPath, on_delete=PROTECT)
    date = DateField(null=True)

    class Meta:
        """Constraints."""

        # prevents None path comics from being duplicated
        unique_together = ["path", "volume", "year", "issue"]

    def _set_date(self):
        """Compute a date for the comic."""
        year = self.year if self.year is not None else datetime.MINYEAR
        month = self.month if self.month is not None else 1
        day = self.day if self.day is not None else 1
        self.date = datetime.date(year, month, day)

    def _get_display_issue(self):
        """Get the issue number, even if its a half issue."""
        if self.issue % 1 == 0:
            issue_str = f"#{int(self.issue):0>3d}"
        else:
            issue_str = f"#{self.issue:.1f0>2d}"
        return issue_str

    def _set_name(self):
        """Set long name for disambiguation."""
        name_list = []
        if self.volume.name:
            name_list.append(f"v{self.volume.name}")
        name_list.append(f"{self.volume.series.name}")
        name_list.append(self._get_display_issue())
        if self.title:
            name_list.append(self.title)
        self.name = " ".join(name_list)

    def _set_display_name(self, short=False):
        """Printable title for comics are usually short."""
        if self.title:
            name = self.title
        else:
            name = self.name
        self.display_name = name

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self._set_date()
        self._set_name()
        # display_name set by super().save()
        super().save(*args, **kwargs)
