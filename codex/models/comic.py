"""Comic model."""

import calendar
import math
import re
from datetime import MAXYEAR, MINYEAR, date
from decimal import Decimal
from pathlib import Path

from comicbox.fields.enum import ReadingDirectionEnum
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    Choices,
    DateField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    ManyToManyField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextField,
)

from codex.models.groups import Imprint, Publisher, Series, Volume
from codex.models.named import (
    AgeRating,
    Character,
    Contributor,
    Country,
    Genre,
    Identifier,
    Language,
    Location,
    OriginalFormat,
    ScanInfo,
    SeriesGroup,
    Story,
    StoryArcNumber,
    Tag,
    Tagger,
    Team,
)
from codex.models.paths import Folder, WatchedPath

__all__ = ("Comic",)


class ReadingDirection(Choices):
    """Reading direction choices."""

    LTR = ReadingDirectionEnum.LTR.value
    RTL = ReadingDirectionEnum.RTL.value
    TTB = ReadingDirectionEnum.TTB.value
    BTT = ReadingDirectionEnum.BTT.value


class Comic(WatchedPath):
    """Comic metadata."""

    class FileType(Choices):
        """Identifiers for file formats."""

        CBZ = "CBZ"
        CBR = "CBR"
        CBT = "CBT"
        PDF = "PDF"

    ORDERING = (
        "series__name",
        "volume__name",
        "issue_number",
        "issue_suffix",
        "name",
        "pk",
    )
    _RE_COMBINE_WHITESPACE = re.compile(r"\s+")

    # From BaseModel, but Comics are sorted by these so index them
    created_at = DateTimeField(auto_now_add=True, db_index=True)
    updated_at = DateTimeField(auto_now=True, db_index=True)

    # From WatchedPath, but interferes with related_name from folders m2m field
    parent_folder = ForeignKey(
        "Folder", on_delete=CASCADE, null=True, related_name="comic_in"
    )

    # Unique comic fields
    issue_number = DecimalField(
        db_index=True, decimal_places=2, max_digits=10, null=True
    )
    issue_suffix = CharField(db_index=True, max_length=16, default="")
    # Group FKs
    volume = ForeignKey(Volume, db_index=True, on_delete=CASCADE)
    series = ForeignKey(Series, db_index=True, on_delete=CASCADE)
    imprint = ForeignKey(Imprint, db_index=True, on_delete=CASCADE)
    publisher = ForeignKey(Publisher, db_index=True, on_delete=CASCADE)
    # Other FKs
    age_rating = ForeignKey(AgeRating, db_index=True, null=True, on_delete=CASCADE)
    original_format = ForeignKey(
        OriginalFormat, null=True, db_index=True, on_delete=CASCADE
    )
    scan_info = ForeignKey(ScanInfo, db_index=True, null=True, on_delete=CASCADE)
    tagger = ForeignKey(Tagger, db_index=True, null=True, on_delete=CASCADE)
    # Alpha2 codes
    country = ForeignKey(Country, db_index=True, null=True, on_delete=CASCADE)
    language = ForeignKey(Language, db_index=True, null=True, on_delete=CASCADE)

    # Date
    year = PositiveSmallIntegerField(db_index=True, null=True)
    month = PositiveSmallIntegerField(null=True)
    day = PositiveSmallIntegerField(null=True)

    # Text
    summary = TextField(default="")
    review = TextField(default="")
    notes = TextField(default="")

    # Ratings
    community_rating = DecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )
    critical_rating = DecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )

    # Reader
    page_count = PositiveSmallIntegerField(db_index=True, default=0)
    reading_direction = CharField(
        db_index=True,
        choices=ReadingDirection.choices,
        default=ReadingDirectionEnum.LTR.value,
        max_length=3,
    )

    # Misc
    monochrome = BooleanField(db_index=True, default=False)

    # ManyToMany
    characters = ManyToManyField(Character)
    contributors = ManyToManyField(Contributor)
    genres = ManyToManyField(Genre)
    identifiers = ManyToManyField(Identifier)
    locations = ManyToManyField(Location)
    series_groups = ManyToManyField(SeriesGroup)
    stories = ManyToManyField(Story)
    story_arc_numbers = ManyToManyField(StoryArcNumber)
    tags = ManyToManyField(Tag)
    teams = ManyToManyField(Team)

    #####################
    # Comicbox Ignored:
    # alternate_issue
    # alternate_volumes
    # cover_image
    # is_version_of
    # last_mark
    # manga
    # price
    # rights

    # codex only
    date = DateField(db_index=True, null=True)
    decade = PositiveSmallIntegerField(db_index=True, null=True)
    folders = ManyToManyField(Folder)
    size = PositiveIntegerField(db_index=True)
    file_type = CharField(
        choices=FileType.choices,
        max_length=3,
        blank=True,
        default="",
    )

    class Meta(WatchedPath.Meta):
        """Constraints."""

        unique_together = ("library", "path")
        verbose_name = "Issue"

    def _set_date(self):
        """Compute a date for the comic."""
        year = MINYEAR if self.year is None else min(max(self.year, MINYEAR), MAXYEAR)
        month = 1 if self.month is None else min(max(self.month, 1), 12)

        if self.day is None:
            day = 1
        else:
            last_day_of_month = calendar.monthrange(year, month)[1]
            day = min(max(self.day, 1), last_day_of_month)

        self.date = date(year, month, day)

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
        self.size = Path(self.path).stat().st_size

    @property
    def max_page(self):
        """Calculate max page from page_count."""
        return max(self.page_count - 1, 0)

    def save(self, *args, **kwargs):
        """Save computed fields."""
        self.presave()
        super().save(*args, **kwargs)

    @staticmethod
    def _compute_zero_pad(issue_number_max):
        """Compute zero padding for issues."""
        if issue_number_max is None:
            issue_number_max = 100
        if issue_number_max < 1:
            return 1
        return math.floor(math.log10(issue_number_max)) + 1

    @classmethod
    def get_title(cls, obj, volume=True, issue_number_max=None, name=True):
        """Create the comic title for display."""
        names = []

        # Series
        if sn := obj.series.name:
            names.append(sn)

        # Volume
        if volume and (vn := obj.volume.name):
            vn = Volume.to_str(vn)
            names.append(vn)

        # Issue
        issue_number = obj.issue_number.normalize() if obj.issue_number else Decimal(0)
        zero_pad = cls._compute_zero_pad(issue_number_max)
        if issue_number % 1 == 0:
            precision = 0
        else:
            precision = 1
            zero_pad += 2
        issue_str = f"#{issue_number:0{zero_pad}.{precision}f}"
        if issue_suffix := obj.issue_suffix:
            issue_str += issue_suffix
        names.append(issue_str)

        # Title
        if name and obj.name:
            names.append(obj.name)

        title = " ".join(filter(None, names)).strip(" .")
        return cls._RE_COMBINE_WHITESPACE.sub(" ", title).strip()

    @classmethod
    def get_filename(cls, obj):
        """Get the fileaname from dict."""
        path = Path(obj.path)
        return path.stem + path.suffix

    def filename(self):
        """Create a filename for download."""
        return self.get_filename(self)

    def __str__(self):
        """Most common text representation for logging."""
        return self.get_title(self)
