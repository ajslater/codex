"""Haystack search indexes."""
from haystack.fields import CharField
from haystack.indexes import Indexable, ModelSearchIndex

from codex.models import Comic


class ComicIndex(ModelSearchIndex, Indexable):
    """Search index for the Comic model."""

    # Related Fields
    publisher = CharField(model_attr="publisher__name")
    imprint = CharField(model_attr="imprint__name")
    series = CharField(model_attr="series__name", boost=1.125)
    volume = CharField(model_attr="volume__name")

    # Many to Many Fields
    characters = CharField(model_attr="characters__name", null=True)
    creators = CharField(model_attr="creators__person__name", null=True)
    genres = CharField(model_attr="genres__name", null=True)
    locations = CharField(model_attr="locations__name", null=True)
    series_groups = CharField(model_attr="series_groups__name", null=True)
    story_arcs = CharField(
        model_attr="story_arcs__name",
        null=True,
    )
    tags = CharField(model_attr="tags__name", null=True)
    teams = CharField(model_attr="teams__name", null=True)

    class Meta:
        """Model & field include list."""

        model = Comic
        # Numeric, Bookean & Date fields.
        fields = (
            "age_rating",
            "comments",
            "community_rating",
            "country",
            "created_at",
            "critical_rating",
            "day",
            "date",
            "decade",
            "issue",
            "issue_suffix",
            "language",
            "month",
            "name",
            "notes",
            "original_format",
            "read_ltr",
            "scan_info",
            "size",
            "summary",
            "page_count",
            "updated_at",
            "user_rating",
            "web",
            "year",
        )

    def get_updated_field(self):
        """To only update models that have changed."""
        return "updated_at"
