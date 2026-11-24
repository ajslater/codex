"""Comicbox tagging serializers."""

from typing import override

from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DictField,
    IntegerField,
    JSONField,
    ListField,
    Serializer,
    ValidationError,
)

from codex.choices.limits import MAX_NAME_LEN
from codex.choices.tagging import NAMED_WRITE_FORMATS, WRITE_FORMATS
from codex.librarian.onlinetag.credential_validator import KNOWN_SOURCES
from codex.librarian.onlinetag.sources import configured_sources
from codex.models import ComicboxTaggingDefaults
from codex.serializers.models.base import BaseModelSerializer


def _validate_ordered_sources(value: list) -> list:
    """
    Validate an ordered source list: known names, deduped, order kept.

    List order is priority: comicbox tries the first source first and, under
    first-wins, its match ends the lookup; when merging, the first source wins
    where sources disagree. So order must survive validation untouched.
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


def _validate_write_formats(value: object) -> list:
    """
    Require at least one tag format the editors offer; dedupe, keep order.

    ``keep`` may ride beside them. Alone it names no format, and comicbox
    then skips an untagged comic without an error, so it is refused. Any
    other value would reach comicbox as is: ``PDF`` rewrites a PDF's
    document metadata.
    """
    if not isinstance(value, list):
        reason = "Expected a list of metadata formats."
        raise ValidationError(reason)
    formats = list(dict.fromkeys(value))
    if unknown := [fmt for fmt in formats if fmt not in WRITE_FORMATS]:
        reason = (
            f"Unknown metadata format(s): {', '.join(map(str, unknown))}. "
            f"Known: {', '.join(WRITE_FORMATS)}."
        )
        raise ValidationError(reason)
    if not any(fmt in NAMED_WRITE_FORMATS for fmt in formats):
        reason = (
            f"At least one metadata format ({', '.join(NAMED_WRITE_FORMATS)})"
            " is required."
        )
        raise ValidationError(reason)
    return formats


class TagWriteRequestSerializer(Serializer):
    """Serializer for tag write requests."""

    collection = CharField()
    pks = ListField(child=CharField())
    patch = CharField(required=False, default="")
    # Comicbox key paths to clear; separate from the patch because a merge
    # write can only add or replace values, never remove them.
    delete_keys = ListField(child=CharField(), required=False, default=list)
    mode = CharField(required=False, default="update")
    formats = ListField(child=CharField(), required=False, default=["COMIC_INFO"])
    delete_original = BooleanField(required=False, default=None)
    # None falls back to the admin ComicboxTaggingDefaults default.
    rename = BooleanField(required=False, default=None)

    @staticmethod
    def validate_formats(value: list) -> list:
        """Only the editors' write formats reach comicbox."""
        return _validate_write_formats(value)


class AdminTagNamesInputSerializer(Serializer):
    """Query params for the tag editor's name suggestions."""

    # None is wider than the name column it matches.
    q = CharField(required=False, allow_blank=True, default="", max_length=MAX_NAME_LEN)
    # Hierarchy scope: the form's current parent names. Blank is unscoped.
    publisher = CharField(
        required=False, allow_blank=True, default="", max_length=MAX_NAME_LEN
    )
    imprint = CharField(
        required=False, allow_blank=True, default="", max_length=MAX_NAME_LEN
    )
    series = CharField(
        required=False, allow_blank=True, default="", max_length=MAX_NAME_LEN
    )


class AdminTagNamesSerializer(Serializer):
    """Existing names for one tag field, at most a capped page of them."""

    field = CharField(read_only=True)
    # Volume names are integers; every other field's are strings.
    names = ListField(child=JSONField(), read_only=True)
    # True when ``names`` is every match, so the client can stop asking.
    complete = BooleanField(read_only=True)


class OnlineTagStartSerializer(Serializer):
    """Serializer for starting an online tagging session."""

    collection = CharField()
    pks = ListField(child=CharField())
    # Omitted: the sources with keys, in the admin's default order. An
    # explicit empty list names no source, which is a 400.
    sources = ListField(child=CharField(), required=False, allow_empty=False)
    mode = ChoiceField(
        choices=ComicboxTaggingDefaults.MatchModeChoices.values,
        required=False,
        default="auto",
    )
    # None falls back to the admin default, like the flags below.
    effort = ChoiceField(
        choices=ComicboxTaggingDefaults.EffortChoices.values,
        required=False,
        default=None,
        allow_null=True,
        allow_blank=True,
    )
    prompts_mode = CharField(required=False, default="ask")
    delete_original = BooleanField(required=False, default=None)
    # None falls back to the admin ComicboxTaggingDefaults default.
    merge_all_sources = BooleanField(required=False, default=None)
    rename = BooleanField(required=False, default=None)
    # Pinned issue ids by source, as entered: an issue URL, ``source:id``,
    # ``4000-id``, or a bare number. A pinned source is fetched by id instead
    # of searched; single-comic sessions only.
    ids = DictField(child=CharField(allow_blank=True), required=False, default=dict)

    @staticmethod
    def validate_sources(value: list) -> list:
        """Require known source names; preserve the priority order."""
        return _validate_ordered_sources(value)

    @staticmethod
    def validate_ids(value: dict) -> dict:
        """Require known source names as the pinned-id keys."""
        unknown = sorted(set(value) - KNOWN_SOURCES)
        if unknown:
            msg = (
                f"Unknown online tagging source(s): {', '.join(unknown)}. "
                f"Known: {', '.join(sorted(KNOWN_SOURCES))}."
            )
            raise ValidationError(msg)
        return value


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
    metron_key = CharField(required=False, allow_blank=True)
    comicvine_key = CharField(required=False, allow_blank=True)
    comicvine_url = CharField(required=False, allow_blank=True)
    versedb_key = CharField(required=False, allow_blank=True)


class TaggingRateLimitWindowSerializer(Serializer):
    """One rate-limit window (burst, hourly or sustained) as limit/remaining."""

    limit = IntegerField(allow_null=True, required=False, default=None)
    remaining = IntegerField(allow_null=True, required=False, default=None)


class TaggingRateLimitsSerializer(Serializer):
    """A source account's live rate limits, from its X-RateLimit-* headers."""

    burst = TaggingRateLimitWindowSerializer()
    hourly = TaggingRateLimitWindowSerializer()
    sustained = TaggingRateLimitWindowSerializer()


class TaggingValidationResultSerializer(Serializer):
    """One source's validation outcome."""

    ok = BooleanField()
    error = CharField(allow_null=True, required=False, default=None)
    rate_limits = TaggingRateLimitsSerializer(
        allow_null=True, required=False, default=None
    )


class TaggingValidateResponseSerializer(Serializer):
    """Response shape for the credential-validation endpoint."""

    results = DictField(child=TaggingValidationResultSerializer())


class ComicboxTaggingDefaultsSerializer(BaseModelSerializer):
    """Serializer for ComicboxTaggingDefaults singleton."""

    metron_key = CharField(write_only=True, required=False, allow_blank=True)
    comicvine_key = CharField(write_only=True, required=False, allow_blank=True)
    versedb_key = CharField(write_only=True, required=False, allow_blank=True)

    metron_key_set = SerializerMethodField()
    comicvine_key_set = SerializerMethodField()
    versedb_key_set = SerializerMethodField()

    has_metron_credentials = SerializerMethodField()
    has_comicvine_credentials = SerializerMethodField()
    has_versedb_credentials = SerializerMethodField()
    configured_sources = SerializerMethodField()

    @staticmethod
    def get_metron_key_set(obj) -> bool:
        """Whether a Metron API key has been configured."""
        return bool(obj.metron_key)

    @staticmethod
    def get_comicvine_key_set(obj) -> bool:
        """Whether a Comic Vine API key has been configured."""
        return bool(obj.comicvine_key)

    @staticmethod
    def get_versedb_key_set(obj) -> bool:
        """Whether a VerseDB API key has been configured."""
        return bool(obj.versedb_key)

    @staticmethod
    def get_has_metron_credentials(obj) -> bool:
        """
        Whether a Metron API key is set.

        Mirrors comicbox's ``MetronOnlineSource.is_configured``.
        """
        return bool(obj.metron_key)

    @staticmethod
    def get_has_comicvine_credentials(obj) -> bool:
        """Whether a Comic Vine API key is set."""
        return bool(obj.comicvine_key)

    @staticmethod
    def get_has_versedb_credentials(obj) -> bool:
        """Whether a VerseDB API key is set."""
        return bool(obj.versedb_key)

    @staticmethod
    def get_configured_sources(obj) -> list[str]:
        """List the supported sources with an API key, in comicbox's order."""
        return list(configured_sources(obj))

    @staticmethod
    def validate_default_formats(value: object) -> list:
        """
        Require at least one known write format.

        comicbox refuses a write with no formats, so an empty default would
        fail every file in an online-tagging session.
        """
        return _validate_write_formats(value)

    @staticmethod
    def validate_default_sources(value: list) -> list:
        """Require known source names; preserve the priority order."""
        return _validate_ordered_sources(value)

    @override
    def to_representation(self, instance) -> dict:
        """
        Read the defaults without a source this build does not register.

        A restore writes ``default_sources`` past the write validation, and
        a later build may register fewer sources. The Tagging tab sends what
        it read back with every auto-save, so a name refused on write would
        make each save a 400; the next save stores the list without it.
        """
        data = super().to_representation(instance)
        data["default_sources"] = [
            source
            for source in data.get("default_sources") or ()
            if source in KNOWN_SOURCES
        ]
        return data

    class Meta(BaseModelSerializer.Meta):
        """Specify model and fields."""

        model = ComicboxTaggingDefaults
        fields = (
            "default_formats",
            "delete_original",
            "rename_files",
            "default_match_mode",
            "default_prompts_mode",
            "default_effort",
            "default_sources",
            "merge_all_sources",
            "metron_key",
            "comicvine_key",
            "versedb_key",
            # Not a secret, so unlike the keys this reads back: the form shows
            # the saved url as its placeholder.
            "comicvine_url",
            "metron_key_set",
            "comicvine_key_set",
            "versedb_key_set",
            "has_metron_credentials",
            "has_comicvine_credentials",
            "has_versedb_credentials",
            "configured_sources",
        )
        read_only_fields = (
            "metron_key_set",
            "comicvine_key_set",
            "versedb_key_set",
            "has_metron_credentials",
            "has_comicvine_credentials",
            "has_versedb_credentials",
            "configured_sources",
        )
