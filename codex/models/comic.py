"""Comic model."""

import calendar
import math
import re
from datetime import MAXYEAR, MINYEAR, date
from pathlib import Path

from comicbox.enums.comicbox import ReadingDirectionEnum
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    ForeignKey,
    ManyToManyField,
    OneToOneField,
    PositiveIntegerField,
    TextField,
)
from typing_extensions import override

from codex.models.base import (
    MAX_ISSUE_SUFFIX_LEN,
    MAX_NAME_LEN,
    BaseModel,
)
from codex.models.choices import (
    FileTypeChoices,
    ReadingDirectionChoices,
    max_choices_len,
)
from codex.models.fields import (
    CleaningCharField,
    CleaningTextField,
    CoercingDecimalField,
    CoercingPositiveSmallIntegerField,
)
from codex.models.groups import (
    Folder,
    Imprint,
    Publisher,
    Series,
    Volume,
    WatchedPathBrowserGroup,
)
from codex.models.identifier import Identifier
from codex.models.named import (
    AgeRating,
    Character,
    Country,
    Credit,
    Genre,
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
    Universe,
)

__all__ = ("Comic",)


class Comic(WatchedPathBrowserGroup):
    """Comic metadata."""

    _ORDERING = (
        "issue_number",
        "issue_suffix",
        "sort_name",
    )
    _RE_COMBINE_WHITESPACE = re.compile(r"\s+")

    # From BaseModel, but Comics are sorted by these so index them
    created_at = DateTimeField(auto_now_add=True, db_index=True)
    updated_at = DateTimeField(auto_now=True, db_index=True)

    # From WatchedPath, but interferes with related_name from folders m2m field
    parent_folder: ForeignKey | None = ForeignKey(
        "Folder", on_delete=CASCADE, null=True, related_name="comic_in"
    )

    # Unique comic fields
    collection_title = CleaningCharField(
        db_index=True,
        max_length=MAX_NAME_LEN,
        default="",
        db_collation="nocase",
    )
    issue_number = CoercingDecimalField(
        db_index=True, decimal_places=2, max_digits=10, null=True
    )
    issue_suffix = CleaningCharField(
        db_index=True,
        max_length=MAX_ISSUE_SUFFIX_LEN,
        default="",
        db_collation="nocase",
    )
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
    main_character = ForeignKey(
        Character,
        db_index=True,
        null=True,
        on_delete=CASCADE,
        related_name="main_character_in_comics",
    )
    main_team = ForeignKey(
        Character,
        db_index=True,
        null=True,
        on_delete=CASCADE,
        related_name="main_team_in_comics",
    )

    # Alpha2 codes
    country = ForeignKey(Country, db_index=True, null=True, on_delete=CASCADE)
    language = ForeignKey(Language, db_index=True, null=True, on_delete=CASCADE)

    # Date
    year = CoercingPositiveSmallIntegerField(db_index=True, null=True)
    month = CoercingPositiveSmallIntegerField(db_index=True, null=True)
    day = CoercingPositiveSmallIntegerField(db_index=True, null=True)

    # Text
    summary = CleaningCharField(default="", db_collation="nocase")
    review = CleaningTextField(default="", db_collation="nocase")
    notes = CleaningTextField(default="", db_collation="nocase")

    # Ratings
    critical_rating = CoercingDecimalField(
        db_index=True, decimal_places=2, max_digits=5, default=None, null=True
    )

    # Reader
    page_count = CoercingPositiveSmallIntegerField(db_index=True, default=0)
    reading_direction = CleaningCharField(
        db_index=True,
        choices=ReadingDirectionChoices.choices,
        default=ReadingDirectionEnum.LTR.value,
        max_length=max_choices_len(ReadingDirectionChoices),
        db_collation="nocase",
    )

    # Misc
    monochrome = BooleanField(db_index=True, default=False)

    # ManyToMany
    characters = ManyToManyField(Character)
    credits = ManyToManyField(Credit)
    genres = ManyToManyField(Genre)
    identifiers = ManyToManyField(Identifier)
    locations = ManyToManyField(Location)
    series_groups = ManyToManyField(SeriesGroup)
    stories = ManyToManyField(Story)
    story_arc_numbers = ManyToManyField(StoryArcNumber)
    tags = ManyToManyField(Tag)
    teams = ManyToManyField(Team)
    universes = ManyToManyField(Universe)

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
    decade = CoercingPositiveSmallIntegerField(db_index=True, null=True)
    folders = ManyToManyField(Folder)
    size = PositiveIntegerField(db_index=True)
    file_type = CleaningCharField(
        db_index=True,
        choices=FileTypeChoices.choices,
        max_length=max_choices_len(FileTypeChoices),
        blank=True,
        default="",
        db_collation="nocase",
    )
    metadata_mtime = DateTimeField(null=True)

    # Not useful
    custom_cover: ForeignKey | None = None

    class Meta(WatchedPathBrowserGroup.Meta):
        """Constraints."""

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

    @override
    def presave(self):
        """Set computed values."""
        super().presave()
        self._set_date()
        self._set_decade()
        self.size = Path(self.path).stat().st_size

    @property
    def max_page(self):
        """Calculate max page from page_count."""
        return max(self.page_count - 1, 0)

    @staticmethod
    def _compute_zero_pad(issue_number_max):
        """Compute zero padding for issues."""
        if issue_number_max is None:
            issue_number_max = 100
        if issue_number_max < 1:
            return 1
        return math.floor(math.log10(issue_number_max)) + 1

    def get_filename(self):
        """Return filename from path as a property."""
        return Path(self.path).name

    @classmethod
    def _get_title_issue_str(cls, obj, zero_pad):
        """Get the issue parts of the title."""
        issue_str = ""
        if obj.issue_number is not None:
            issue_number = obj.issue_number.normalize()
            if not zero_pad:
                zero_pad = 3
            if issue_number % 1 == 0:
                precision = 0
            else:
                precision = 1
                zero_pad += 2
            issue_str = f"#{issue_number:0{zero_pad}.{precision}f}"
        if issue_suffix := obj.issue_suffix:
            issue_str += issue_suffix
        return issue_str

    @classmethod
    def get_title(
        cls, obj, *, volume: bool, name: bool, filename_fallback: bool, zero_pad=None
    ) -> str:
        """Create the comic title for display."""
        if not obj:
            return ""

        names = []
        # Series
        if sn := obj.series.name:
            names.append(sn)

        # Volume
        if volume and (vn := obj.volume.name):
            vn_to = obj.volume.number_to
            vn = Volume.to_str(vn, vn_to)
            names.append(vn)

        # Issue
        if issue_str := cls._get_title_issue_str(obj, zero_pad):
            names.append(issue_str)

        # Title
        if name and obj.name:
            names.append(obj.name)

        title = " ".join(filter(None, names)).strip(" .")
        title = cls._RE_COMBINE_WHITESPACE.sub(" ", title).strip()
        if filename_fallback and not title:
            title = obj.get_filename()
        return title

    @override
    def __repr__(self):
        """Most common text representation for logging."""
        return self.get_title(self, volume=True, name=True, filename_fallback=True)


class ComicFTS(BaseModel):
    comic = OneToOneField(primary_key=True, to=Comic, on_delete=CASCADE)
    # Attributes
    collection_title = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    name = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    review = TextField(db_collation="nocase")
    summary = TextField(db_collation="nocase")
    # FK groups
    publisher = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    imprint = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    series = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    # FK
    age_rating = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    country = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    language = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    original_format = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    scan_info = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    tagger = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    # M2M
    characters = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    credits = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    genres = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    sources = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    locations = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    series_groups = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    stories = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    story_arcs = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    tags = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    teams = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)
    universes = CharField(db_collation="nocase", max_length=MAX_NAME_LEN)

    class Meta(BaseModel.Meta):
        managed = False
