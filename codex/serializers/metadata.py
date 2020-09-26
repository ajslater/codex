"""Codex Serializers for the metadata box."""
from rest_framework.serializers import BooleanField
from rest_framework.serializers import CharField
from rest_framework.serializers import DecimalField
from rest_framework.serializers import IntegerField
from rest_framework.serializers import ListField
from rest_framework.serializers import ModelSerializer
from rest_framework.serializers import Serializer
from rest_framework.serializers import URLField

from codex.models import Credit
from codex.models import UserBookmark
from codex.serializers.vuetify import VueCountryChoiceSerializer
from codex.serializers.vuetify import VueIntChoiceSerializer
from codex.serializers.vuetify import VueLanguageChoiceSerializer


class CreditSerializer(ModelSerializer):
    """Credit model serializer."""

    person = VueIntChoiceSerializer(read_only=True)
    role = VueIntChoiceSerializer(read_only=True)

    class Meta:
        """Model spec."""

        model = Credit
        fields = ("pk", "person", "role")
        read_only_fields = fields


class MetadataSerializer(Serializer):
    """Serialize the comic model for browser metadata box."""

    # All the comic pks for a filtered aggregate group
    pks = ListField(child=IntegerField())

    # Aggregate Annotations
    size = IntegerField()
    coverPath = CharField()  # noqa: N815

    # UserBookmark annotations
    # fit_to = CharField()
    # two_pages = BooleanField()
    bookmark = IntegerField()
    finished = BooleanField()
    pageCount = IntegerField()  # noqa: N815
    progress = DecimalField(max_digits=5, decimal_places=2)

    # Publish annotations
    publisherChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    imprintChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    seriesChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    volumeChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    volumeCountChoices = VueIntChoiceSerializer(  # noqa: N815
        many=True, allow_null=True
    )
    issueCountChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815

    # Value Choices
    issueChoices = ListField(  # noqa: N815
        child=DecimalField(max_digits=5, decimal_places=1), allow_null=True
    )
    titleChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    yearChoices = ListField(child=IntegerField(), allow_null=True)  # noqa: N815
    monthChoices = ListField(child=IntegerField(), allow_null=True)  # noqa: N815
    dayChoices = ListField(child=IntegerField(), allow_null=True)  # noqa: N815
    formatChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    readLTRChoices = ListField(child=BooleanField(), allow_null=True)  # noqa: N815
    webChoices = ListField(child=URLField(), allow_null=True)  # noqa: N815
    userRatingChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    criticalRatingChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    maturityRatingChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    scanInfoChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    # Too big for choices and doesn't really make sense anyway
    # summaryChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    # descriptionChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    # notesChoices = ListField(child=CharField(), allow_null=True)  # noqa: N815
    summary = CharField(allow_null=True)
    description = CharField(allow_null=True)
    notes = CharField(allow_null=True)
    countryChoices = VueCountryChoiceSerializer(  # noqa: N815
        many=True, allow_null=True
    )
    languageChoices = VueLanguageChoiceSerializer(  # noqa: N815
        many=True, allow_null=True
    )

    # Many to Many Choices
    genresChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    tagsChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    teamsChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    charactersChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    locationsChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    seriesGroupsChoices = VueIntChoiceSerializer(  # noqa: N815
        many=True, allow_null=True
    )
    storyArcsChoices = VueIntChoiceSerializer(many=True, allow_null=True)  # noqa: N815
    creditsChoices = CreditSerializer(many=True, allow_null=True)  # noqa: N815


class UserBookmarkFinishedSerializer(ModelSerializer):
    """The finished field of the UserBookmark."""

    class Meta:
        """Model spec."""

        model = UserBookmark
        fields = ("finished",)
