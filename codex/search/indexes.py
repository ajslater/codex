"""Haystack search indexes."""
from haystack.fields import CharField
from haystack.indexes import Indexable, ModelSearchIndex
from whoosh.analysis import CharsetFilter, StandardAnalyzer, StemFilter
from whoosh.support.charset import accent_map

from codex.models import Comic


class CCharField(CharField):
    """A Charfield that uses codex's specific text analyzer."""

    TEXT_ANALYZER = (
        StandardAnalyzer() | CharsetFilter(accent_map) | StemFilter(cachesize=-1)
    )

    def __init__(self, *args, **kwargs):
        """Initialize with the analyzer param."""
        super().__init__(*args, analyzer=self.TEXT_ANALYZER, **kwargs)


class ComicIndex(ModelSearchIndex, Indexable):
    """Search index for the Comic model."""

    # Char fields
    comments = CCharField(model_attr="comments", null=True)
    country = CCharField(model_attr="country", null=True)
    original_format = CCharField(model_attr="original_format", null=True)
    language = CCharField(model_attr="language", null=True)
    name = CCharField(model_attr="name", null=True)
    notes = CCharField(model_attr="notes", null=True)
    summary = CCharField(model_attr="summary", null=True)
    scan_info = CCharField(model_attr="scan_info", null=True)
    web = CCharField(model_attr="web", null=True)

    # Related Fields
    publisher = CCharField(model_attr="publisher__name")
    imprint = CCharField(model_attr="imprint__name")
    series = CCharField(model_attr="series__name", boost=1.125)
    volume = CCharField(model_attr="volume__name")

    # Many to Many Fields
    characters = CCharField(model_attr="characters__name", null=True)
    creators = CCharField(model_attr="creators__person__name", null=True)
    genres = CCharField(model_attr="genres__name", null=True)
    locations = CCharField(model_attr="locations__name", null=True)
    series_groups = CCharField(model_attr="series_groups__name", null=True)
    story_arcs = CCharField(
        model_attr="story_arcs__name",
        null=True,
    )
    tags = CCharField(model_attr="tags__name", null=True)
    teams = CCharField(model_attr="teams__name", null=True)

    class Meta:
        """Model & field include list."""

        model = Comic
        # Numeric, Bookean & Date fields.
        fields = (
            "age_rating",
            "community_rating",
            "created_at",
            "critical_rating",
            "day",
            "date",
            "decade",
            "issue",
            "issue_suffix",
            "month",
            "read_ltr",
            "size",
            "page_count",
            "updated_at",
            "user_rating",
            "year",
        )

    def get_updated_field(self):
        """To only update models that have changed."""
        return "updated_at"
