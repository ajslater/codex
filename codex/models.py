"""Codex Django Models."""
from django.contrib.auth.models import User
from django.db.models import CASCADE
from django.db.models import PROTECT
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

from .validators import validate_path_exists


DEFAULT_SCAN_FREQUENCY = 12 * 60 * 60


class RootPath(Model):
    """The root path the comic file live under."""

    path = CharField(unique=True, max_length=128, validators=[validate_path_exists])
    scan_frequency = DurationField(default=DEFAULT_SCAN_FREQUENCY)
    last_scan = DateTimeField(null=True)


class Genre(Model):
    """The genre the comic belongs to."""

    name = CharField(max_length=32, primary_key=True)


class Publisher(Model):
    """The publisher of the comic."""

    name = CharField(max_length=32, primary_key=True)


class Series(Model):
    """The series the comic belongs to."""

    name = CharField(max_length=32)
    year = PositiveSmallIntegerField(null=True)
    volume = PositiveSmallIntegerField(null=True)

    class Meta:
        """Constraints."""

        unique_together = ["name", "year", "volume"]


class SeriesGroup(Model):
    """A series group the series is part of."""

    name = CharField(max_length=32, primary_key=True)


class StoryArc(Model):
    """A story arc the comic is part of."""

    name = CharField(max_length=32, primary_key=True)


class Location(Model):
    """A location that appears in the comic."""

    name = CharField(max_length=32, primary_key=True)


class Character(Model):
    """A character that appears in the comic."""

    name = CharField(max_length=32, primary_key=True)


class Team(Model):
    """A team that appears in the comic."""

    name = CharField(max_length=32, primary_key=True)


class Tag(Model):
    """Arbitrary Metadata Tag."""

    name = CharField(max_length=16, primary_key=True)


class CreditRole(Model):
    """A role for the credited person. Writer, Inker, etc."""

    name = CharField(max_length=16, primary_key=True)


class Credit(Model):
    """A creator credit."""

    person = CharField(max_length=32)
    role = ForeignKey(CreditRole, on_delete=CASCADE)

    class Meta:
        """Constraints."""

        unique_together = ["person", "role"]


class Imprint(Model):
    """A Publishing imprint."""

    name = CharField(max_length=32)
    publisher = ForeignKey(Publisher, on_delete=CASCADE)

    class Meta:
        """Constraints."""

        unique_together = ["name", "publisher"]


class Comic(Model):
    """Comic metadata."""

    path = CharField(max_length=128, null=True)
    genre = ForeignKey(Genre, on_delete=PROTECT, null=True)
    issue = PositiveSmallIntegerField()
    language = CharField(max_length=2, null=True)
    publisher = ForeignKey(Publisher, on_delete=PROTECT, null=True)
    series = ForeignKey(Series, on_delete=PROTECT)
    title = CharField(max_length=64, null=True)
    publish_date = DateField(null=True)
    volume = PositiveSmallIntegerField(null=True)
    comments = TextField(null=True)
    issue_count = PositiveSmallIntegerField(null=True)
    read_ltr = BooleanField(default=True)
    critical_rating = CharField(max_length=32, null=True)
    alternate_issue = PositiveSmallIntegerField(null=True)
    alternate_issue_count = PositiveSmallIntegerField(null=True)
    alternate_series = ForeignKey(
        Series, on_delete=PROTECT, related_name="alternate_comics", null=True
    )
    black_and_white = BooleanField(default=False)
    manga = BooleanField(default=False)
    maturity_rating = CharField(max_length=32, null=True)
    notes = TextField(null=True)
    scan_info = CharField(max_length=32, null=True)
    series_group = ForeignKey(SeriesGroup, on_delete=PROTECT, null=True)
    story_arc = ForeignKey(StoryArc, on_delete=PROTECT, null=True)
    web = URLField(null=True)
    country = CharField(max_length=2, null=True)
    user_rating = CharField(max_length=32, null=True)
    volume_count = PositiveSmallIntegerField(null=True)
    cover_image = CharField(max_length=64, null=True)
    description = TextField(null=True)
    book_format = CharField(max_length=16, null=True)
    identifier = CharField(max_length=64, null=True)
    last_mark = PositiveSmallIntegerField(null=True)
    price = DecimalField(decimal_places=2, max_digits=9, null=True)
    rights = CharField(max_length=64, null=True)
    page_count = PositiveSmallIntegerField()
    is_version_of = CharField(max_length=64, null=True)
    imprint = ForeignKey(Imprint, on_delete=PROTECT, null=True)
    credits = ManyToManyField(Credit)
    tags = ManyToManyField(Tag)
    teams = ManyToManyField(Team)
    characters = ManyToManyField(Character)
    locations = ManyToManyField(Location)

    # codex only
    root_path = ForeignKey(RootPath, on_delete=CASCADE)


class UserComic(Model):
    """User's indivual records about a comic."""

    user = ForeignKey(User, on_delete=CASCADE)
    comic = ForeignKey(Comic, on_delete=CASCADE)
    bookmark = PositiveSmallIntegerField()
    finished = BooleanField()
    rating = PositiveSmallIntegerField()

    class Meta:
        """Constraints."""

        unique_together = ["user", "comic"]
