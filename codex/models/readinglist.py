"""
Reading list models.

A reading list is a named, ordered set of issues behind the browser's
``arcs`` collection. Its contents come from one or more sources: the
story-arc tags in comic files, an uploaded or fetched list file, a
Metron reading list or story arc, a Comic Vine story arc. Codex keeps
what each source delivered and computes the list from them, so a list
can be refreshed, a source added later and a combination undone.

None of these models is owned by the importer. They must never enter
the janitor's ``_FK_MODELS``, and nothing here holds a reverse relation
to an importer-owned model: the janitor keeps any row that has one alive.
The one link into the library hierarchy, a series mapping's ``series``,
hides its reverse accessor (``related_name="+"``) for that reason.
"""

from typing import Final, override
from uuid import uuid4

from django.conf import settings
from django.db.models import (
    CASCADE,
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    Index,
    JSONField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    Q,
    TextChoices,
    UniqueConstraint,
    UUIDField,
)

from codex.choices.limits import MAX_NAME_LEN
from codex.choices.readinglists import ReadingListSourceKind
from codex.collection import COLLECTION_LABELS, Collection
from codex.models.base import BaseModel
from codex.models.choices import max_choices_len
from codex.models.collections import BrowserCollectionModel, Series
from codex.models.comic import Comic
from codex.models.fields import CleaningCharField, CleaningTextField

__all__ = (
    "ITEM_COLLECTIONS",
    "ReadingList",
    "ReadingListEntry",
    "ReadingListMatchTier",
    "ReadingListSeriesMapping",
    "ReadingListSource",
    "ReadingListSourceKind",
)

# Long enough for a URL or a catalog path; a remote id or arc name is far
# shorter. Kept below SQLite's practical index width.
MAX_REF_LEN: Final[int] = 1024
MAX_REVISION_LEN: Final[int] = 128
MAX_ISSUE_LEN: Final[int] = 32
# The collections a list holds whole, as items that stay current. A comic is
# an entry, never an item.
ITEM_COLLECTIONS: Final = (
    Collection.PUBLISHER,
    Collection.IMPRINT,
    Collection.SERIES,
    Collection.VOLUME,
    Collection.FOLDER,
    Collection.ARC,
)
_ITEM_COLLECTION_CHOICES: Final = tuple(
    (collection.value, COLLECTION_LABELS[collection]) for collection in ITEM_COLLECTIONS
)


class ReadingListMatchTier(TextChoices):
    """How an entry's comic was found, strongest first."""

    NONE = "", "Missing"
    # A person said the library does not have it: nothing rematches it.
    MARKED_MISSING = "marked_missing", "Marked missing"
    MANUAL = "manual", "By hand"
    TAGGED = "tagged", "Tagged"
    MAPPING = "mapping", "Series mapping"
    ISSUE_ID = "issue_id", "Issue id"
    SERIES_ID = "series_id", "Series id"
    EXACT_NAME = "exact_name", "Exact name"
    NORMALIZED_NAME = "normalized_name", "Normalized name"
    # Delivered by a collection item: a comic of the series, folder or list.
    COLLECTION = "collection", "From a collection"


class ReadingList(BrowserCollectionModel):
    """
    A named, ordered list of issues.

    ``user`` NULL is a global list, visible to everyone the comics are.
    Global names need not be unique: one event has several curated orders.
    A user's personal list names are unique per user.
    """

    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=CASCADE,
        null=True,
        blank=True,
        default=None,
        db_index=True,
    )
    # Identity that survives a backup and restore, and the file UUID a
    # json-cbl export carries so repeated exports name one list.
    uuid = UUIDField(default=uuid4, unique=True, editable=False)
    description = CleaningTextField(blank=True, default="")
    # Not ``notes``: the metadata view annotates Comic's ``notes`` onto the
    # browsed row, and a field of that name on the row refuses it.
    list_notes = CleaningTextField(blank=True, default="")
    list_type = CleaningCharField(max_length=64, blank=True, default="")
    start_year = PositiveSmallIntegerField(null=True, default=None)
    end_year = PositiveSmallIntegerField(null=True, default=None)
    # Header fields a person changed by hand. A recombine leaves them be.
    edited_fields = JSONField(default=list)
    # A hand reorder locks the order: a recompute never moves an existing
    # entry, only inserts new ones beside their neighbours.
    order_locked = BooleanField(default=False)
    # Carried only for export: previous and next list, tags.
    extra = JSONField(default=dict)

    class Meta(BrowserCollectionModel.Meta):
        """Personal list names are unique per owner."""

        constraints = (
            UniqueConstraint(
                fields=("user", "name"),
                condition=Q(user__isnull=False),
                name="unique_readinglist_user_name",
            ),
        )

    @override
    def __repr__(self) -> str:
        return f"<ReadingList pk={self.pk}>"


class ReadingListSource(BaseModel):
    """One source of a reading list's entries."""

    reading_list = ForeignKey(ReadingList, on_delete=CASCADE, related_name="sources")
    kind = CharField(
        max_length=max_choices_len(ReadingListSourceKind),
        choices=ReadingListSourceKind.choices,
        db_index=True,
    )
    # The arc sort name, filename, URL, catalog path or remote id.
    ref = CharField(max_length=MAX_REF_LEN, db_index=True)
    # A blob sha, modified stamp, or for tags a digest of the tagged comics.
    revision = CharField(max_length=MAX_REVISION_LEN, blank=True, default="")
    # Who curated the order (CBRO, CMRO, a Metron user), shown in the UI.
    attribution_source = CleaningCharField(
        max_length=MAX_NAME_LEN, blank=True, default=""
    )
    attribution_url = CharField(max_length=MAX_REF_LEN, blank=True, default="")
    # Precedence among the list's sources; the lowest is the primary.
    rank = PositiveSmallIntegerField(default=0)
    # Whether this source's order is authoritative.
    ordered = BooleanField(default=True)
    # The comicbox reading list as fetched. NULL for tags, whose document
    # is built from the tag tables when it is needed.
    document = JSONField(null=True, default=None)
    fetched_at = DateTimeField(null=True, default=None)
    # A collection item's collection and the row it is bound to. A NULL
    # target is dangling: the series went, and ``ref`` finds it again.
    collection = CharField(
        max_length=16, choices=_ITEM_COLLECTION_CHOICES, blank=True, default=""
    )
    target_id = PositiveIntegerField(null=True, default=None)
    # Where an item with no comics sits: how many of the list's other
    # entries come before it. NULL is the end. Only the live sync writes it.
    position = PositiveIntegerField(null=True, default=None)

    class Meta(BaseModel.Meta):
        """
        A list holds one source per reference, and one item per row.

        A collection item's ``ref`` is its identity, which two folders in
        different libraries can share, so items are unique by target.
        """

        constraints = (
            UniqueConstraint(
                fields=("reading_list", "kind", "ref"),
                condition=~Q(kind=ReadingListSourceKind.COLLECTION),
                name="unique_readinglistsource_list_kind_ref",
            ),
            UniqueConstraint(
                fields=("reading_list", "collection", "target_id"),
                condition=Q(target_id__isnull=False),
                name="unique_readinglistsource_list_item",
            ),
        )
        indexes = (Index(fields=("kind", "ref"), name="readinglistsource_kind_ref"),)

    @override
    def __repr__(self) -> str:
        return f"<ReadingListSource pk={self.pk} kind={self.kind}>"


class ReadingListEntry(BaseModel):
    """
    One position in a reading list.

    Missing is derived, never stored: an entry is missing when ``comic``
    is NULL and it is not ignored. Every entry keeps a ``reference``, the
    comicbox entry it stands for, so a comic removed and re-added is
    found again, unless a person marked it missing.
    """

    reading_list = ForeignKey(ReadingList, on_delete=CASCADE, related_name="entries")
    # Dense and zero-based. Not unique: SQLite cannot defer a unique
    # constraint across a bulk reorder, so ties break on pk.
    position = PositiveIntegerField(default=0)
    comic = ForeignKey(
        Comic,
        on_delete=SET_NULL,
        null=True,
        default=None,
        related_name="reading_list_entries",
    )
    reference = JSONField(default=dict)
    series_name = CleaningCharField(max_length=MAX_NAME_LEN, blank=True, default="")
    issue = CharField(max_length=MAX_ISSUE_LEN, blank=True, default="")
    year = PositiveSmallIntegerField(null=True, default=None)
    match_tier = CharField(
        max_length=max_choices_len(ReadingListMatchTier),
        choices=ReadingListMatchTier.choices,
        blank=True,
        default=ReadingListMatchTier.NONE,
    )
    needs_review = BooleanField(default=False, db_index=True)
    ignored = BooleanField(default=False)
    manual = BooleanField(default=False)
    entry_type = CharField(max_length=32, blank=True, default="")
    # Pks of the list's sources that contributed this entry.
    source_ids = JSONField(default=list)
    # The collection item that delivers this entry's comic. Such a live
    # entry is the live sync's alone: no person edits it and no recompute
    # reads it, and it goes with its item.
    live_source = ForeignKey(
        ReadingListSource,
        on_delete=CASCADE,
        null=True,
        default=None,
        related_name="live_entries",
    )

    class Meta(BaseModel.Meta):
        """Read in list order."""

        verbose_name_plural = "reading list entries"
        indexes = (
            Index(
                fields=("reading_list", "position"),
                name="readinglistentry_list_pos",
            ),
            Index(
                fields=("comic", "reading_list"),
                name="readinglistentry_comic_list",
            ),
        )

    @override
    def __repr__(self) -> str:
        return f"<ReadingListEntry pk={self.pk} position={self.position}>"


class ReadingListSeriesMapping(BaseModel):
    """
    A saved answer: a list's series is this library series.

    Made in review ("all 14 missing issues of this series belong here")
    and applied to every list. ``series_key`` is comicbox's normalized
    series name; ``year`` is the volume or start year that tells two
    series of one name apart, or 0 when the list gave none. Not NULL:
    SQLite treats NULLs as distinct in a unique constraint.
    """

    series_key = CharField(max_length=MAX_NAME_LEN, db_index=True)
    year = PositiveSmallIntegerField(default=0)
    # Hidden reverse accessor: see the module docstring.
    series = ForeignKey(Series, on_delete=CASCADE, related_name="+")

    class Meta(BaseModel.Meta):
        """One answer per series name and year."""

        constraints = (
            UniqueConstraint(
                fields=("series_key", "year"),
                name="unique_readinglistseriesmapping_key_year",
            ),
        )

    @override
    def __repr__(self) -> str:
        return f"<ReadingListSeriesMapping pk={self.pk}>"
