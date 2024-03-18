"""Haystack search indexes."""

from codex._vendor.haystack.fields import CharField, IntegerField
from codex._vendor.haystack.indexes import Indexable, ModelSearchIndex
from codex.models import Comic


class ComicIndex(ModelSearchIndex, Indexable):
    """Search index for the Comic model."""

    # Groups
    publisher = CharField(model_attr="publisher__name")
    imprint = CharField(model_attr="imprint__name")
    series = CharField(model_attr="series__name", boost=1.125)
    volume = IntegerField(model_attr="volume__name", null=True)

    # Related Fields
    age_rating = CharField(model_attr="age_rating__name", null=True)
    country = CharField(model_attr="country__name", null=True)
    language = CharField(model_attr="language__name", null=True)
    original_format = CharField(model_attr="original_format__name", null=True)
    scan_info = CharField(model_attr="scan_info__name", null=True)
    tagger = CharField(model_attr="tagger__name", null=True)

    # Many to Many Fields
    characters = CharField(model_attr="characters__name", null=True)
    contributors = CharField(model_attr="contributors__person__name", null=True)
    genres = CharField(model_attr="genres__name", null=True)
    locations = CharField(model_attr="locations__name", null=True)
    identifier = CharField(model_attr="identifiers__nss", null=True)
    identifier_type = CharField(
        model_attr="identifiers__identifier_type__name", null=True
    )
    series_groups = CharField(model_attr="series_groups__name", null=True)
    stories = CharField(model_attr="stories__name", null=True)
    story_arcs = CharField(
        model_attr="story_arc_numbers__story_arc__name",
        null=True,
    )
    tags = CharField(model_attr="tags__name", null=True)
    teams = CharField(model_attr="teams__name", null=True)

    class Meta:
        """Model & field include list."""

        model = Comic
        fields = (
            "community_rating",
            "created_at",
            "critical_rating",
            "day",
            "date",
            "decade",
            "issue_number",
            "issue_suffix",
            "month",
            "monochrome",
            "name",
            "notes",
            "page_count",
            "reading_direction",
            "review",
            "size",
            "summary",
            "updated_at",
            "user_rating",
            "year",
        )

    def get_updated_field(self):  # type: ignore
        """To only update models that have changed."""
        return "updated_at"
