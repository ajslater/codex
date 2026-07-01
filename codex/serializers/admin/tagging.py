"""Comicbox tagging serializers."""

from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DictField,
    ListField,
    Serializer,
    ValidationError,
)

from codex.librarian.onlinetag.credential_validator import KNOWN_SOURCES
from codex.models import ComicboxTaggingDefaults
from codex.serializers.models.base import BaseModelSerializer


def _validate_ordered_sources(value: list) -> list:
    """
    Validate an ordered source list: known names, deduped, order kept.

    List order is run priority (comicbox tries the first source first and,
    under first-wins, its match ends the lookup), so order must survive
    validation untouched.
    """
    sources = list(dict.fromkeys(value))
    unknown = [s for s in sources if s not in KNOWN_SOURCES]
    if unknown:
        msg = (
            f"Unknown online tagging source(s): {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(KNOWN_SOURCES))}."
        )
        raise ValidationError(msg)
    return sources


class TagWriteRequestSerializer(Serializer):
    """Serializer for tag write requests."""

    collection = CharField()
    pks = ListField(child=CharField())
    patch = CharField(required=False, default="")
    mode = CharField(required=False, default="update")
    formats = ListField(child=CharField(), required=False, default=["COMIC_INFO"])
    delete_original = BooleanField(required=False, default=None)
    # None falls back to the admin ComicboxTaggingDefaults default.
    rename = BooleanField(required=False, default=None)


class OnlineTagStartSerializer(Serializer):
    """Serializer for starting an online tagging session."""

    collection = CharField()
    pks = ListField(child=CharField())
    sources = ListField(
        child=CharField(), required=False, default=["metron", "comicvine"]
    )
    mode = CharField(required=False, default="auto")
    prompts_mode = CharField(required=False, default="ask")
    effort = CharField(required=False, default="balanced")
    auto_threshold = CharField(required=False, default="0.85")
    dry_run = CharField(required=False, default="false")
    delete_original = BooleanField(required=False, default=None)
    # None falls back to the admin ComicboxTaggingDefaults default.
    merge_all_sources = BooleanField(required=False, default=None)
    rename = BooleanField(required=False, default=None)

    @staticmethod
    def validate_sources(value: list) -> list:
        """Require known source names; preserve the priority order."""
        return _validate_ordered_sources(value)


class TagByIdRequestSerializer(Serializer):
    """Serializer for tagging one comic by a known online issue id."""

    collection = CharField()
    pk = CharField()
    identifier = CharField()
    source = CharField(required=False, allow_blank=True, default="")
    # All identifiers entered (one per source) when merging by id; the primary
    # ``identifier`` is the first. Ignored unless merging.
    identifiers = ListField(child=CharField(), required=False, default=list)
    # None falls back to the admin ComicboxTaggingDefaults default.
    merge_all_sources = BooleanField(required=False, default=None)
    rename = BooleanField(required=False, default=None)


class OnlineTagPromptResponseSerializer(Serializer):
    """Serializer for admin response to an online tag prompt."""

    action = CharField()
    payload = CharField(required=False, allow_blank=True, default="")
    chosen_volume_id = CharField(required=False, allow_blank=True, default="")


class TaggingValidateRequestSerializer(Serializer):
    """Validate credentials, optionally overriding stored values from the form."""

    source = ChoiceField(
        choices=tuple(sorted(KNOWN_SOURCES)), required=False, allow_blank=True
    )
    metron_user = CharField(required=False, allow_blank=True)
    metron_password = CharField(required=False, allow_blank=True)
    metron_url = CharField(required=False, allow_blank=True)
    comicvine_key = CharField(required=False, allow_blank=True)
    comicvine_url = CharField(required=False, allow_blank=True)


class TaggingValidationResultSerializer(Serializer):
    """One source's validation outcome."""

    ok = BooleanField()
    error = CharField(allow_null=True, required=False, default=None)


class TaggingValidateResponseSerializer(Serializer):
    """Response shape for the credential-validation endpoint."""

    results = DictField(child=TaggingValidationResultSerializer())


class ComicboxTaggingDefaultsSerializer(BaseModelSerializer):
    """Serializer for ComicboxTaggingDefaults singleton."""

    metron_user = CharField(write_only=True, required=False, allow_blank=True)
    metron_password = CharField(write_only=True, required=False, allow_blank=True)
    comicvine_key = CharField(write_only=True, required=False, allow_blank=True)

    metron_user_set = SerializerMethodField()
    metron_password_set = SerializerMethodField()
    comicvine_key_set = SerializerMethodField()

    has_metron_credentials = SerializerMethodField()
    has_comicvine_credentials = SerializerMethodField()

    @staticmethod
    def get_metron_user_set(obj) -> bool:
        """Whether a Metron username has been configured."""
        return bool(obj.metron_user)

    @staticmethod
    def get_metron_password_set(obj) -> bool:
        """Whether a Metron password has been configured."""
        return bool(obj.metron_password)

    @staticmethod
    def get_comicvine_key_set(obj) -> bool:
        """Whether a Comic Vine API key has been configured."""
        return bool(obj.comicvine_key)

    @staticmethod
    def get_has_metron_credentials(obj) -> bool:
        """Whether both Metron username and password are set."""
        return bool(obj.metron_user and obj.metron_password)

    @staticmethod
    def get_has_comicvine_credentials(obj) -> bool:
        """Whether a Comic Vine API key is set."""
        return bool(obj.comicvine_key)

    @staticmethod
    def validate_default_sources(value: list) -> list:
        """Require known source names; preserve the priority order."""
        return _validate_ordered_sources(value)

    class Meta(BaseModelSerializer.Meta):
        """Specify model and fields."""

        model = ComicboxTaggingDefaults
        fields = (
            "default_formats",
            "delete_original",
            "rename_files",
            "default_match_mode",
            "default_prompts_mode",
            "default_sources",
            "merge_all_sources",
            "metron_user",
            "metron_password",
            "metron_url",
            "comicvine_key",
            "comicvine_url",
            "metron_user_set",
            "metron_password_set",
            "comicvine_key_set",
            "has_metron_credentials",
            "has_comicvine_credentials",
        )
        read_only_fields = (
            "metron_user_set",
            "metron_password_set",
            "comicvine_key_set",
            "has_metron_credentials",
            "has_comicvine_credentials",
        )
