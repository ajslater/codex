"""Haystack search indexes."""

from haystack.fields import CharField, DateField, MultiValueField
from haystack.indexes import Indexable, ModelSearchIndex

from codex.models import Comic


class ComicIndex(ModelSearchIndex, Indexable):
    """Search index for the Comic model."""

    # ModeSearchIndex tries to use datetime, incorrectly
    # This seems like a haystack bug
    # https://github.com/django-haystack/django-haystack/issues/1829
    date = DateField(model_attr="date", null=True, default=None)

    # Related Fields
    publisher = CharField(model_attr="publisher__name")
    imprint = CharField(model_attr="imprint__name")
    series = CharField(model_attr="series__name", boost=1.125)
    volume = CharField(model_attr="volume__name")

    # Many to Many Fields
    characters = MultiValueField(model_attr="characters__name", null=True)
    creators = MultiValueField(model_attr="credits__person__name", null=True)
    genres = MultiValueField(model_attr="genres__name", null=True)
    locations = MultiValueField(model_attr="locations__name", null=True)
    series_groups = MultiValueField(model_attr="series_groups__name", null=True)
    story_arcs = MultiValueField(model_attr="story_arcs__name", null=True)
    tags = MultiValueField(model_attr="tags__name", null=True)
    teams = MultiValueField(model_attr="teams__name", null=True)

    class Meta:
        """Model & field include list."""

        model = Comic
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
            "format",
            "issue",
            "issue_suffix",
            "language",
            "month",
            "read_ltr",
            "name",
            "notes",
            "page_count",
            "scan_info",
            "size",
            "summary",
            "updated_at",
            "user_rating",
            "web",
            "year",
        )

    def get_updated_field(self):
        """To only update models that have changed."""
        return "updated_at"
