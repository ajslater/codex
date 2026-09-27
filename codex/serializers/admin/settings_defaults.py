"""SettingsDefaults admin serializer."""

from collections.abc import Mapping
from typing import Any, override

from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DictField,
    ListField,
    Serializer,
    ValidationError,
)

from codex.choices.browser import (
    BROWSER_BOOKMARK_FILTER_CHOICES,
    BROWSER_TOP_COLLECTION_CHOICES,
    BROWSER_VIEW_MODE_CHOICES,
    SETTINGS_DEFAULTS_ORDER_BY_CHOICES,
    SHOW_COLLECTIONS,
    clean_table_columns,
    coherent_top_collection,
)
from codex.models.admin import SettingsDefaults
from codex.serializers.fields import FitToField, ReadingDirectionField
from codex.settings.db import folder_view_on

_VERTICAL_READING_DIRECTIONS = frozenset({"ttb", "btt"})


class SettingsDefaultsBrowserSerializer(Serializer):
    """Site default browser settings, flat columns on the singleton."""

    top_collection = ChoiceField(choices=tuple(BROWSER_TOP_COLLECTION_CHOICES.keys()))
    show_publishers = BooleanField()
    show_imprints = BooleanField()
    show_series = BooleanField()
    show_volumes = BooleanField()
    order_by = ChoiceField(
        choices=tuple(SETTINGS_DEFAULTS_ORDER_BY_CHOICES.keys()), allow_blank=True
    )
    order_reverse = BooleanField()
    view_mode = ChoiceField(choices=tuple(BROWSER_VIEW_MODE_CHOICES.keys()))
    twenty_four_hour_time = BooleanField()
    always_show_filename = BooleanField()
    bookmark = ChoiceField(
        choices=tuple(BROWSER_BOOKMARK_FILTER_CHOICES.keys()), allow_blank=True
    )
    table_columns = DictField(
        child=ListField(child=CharField(), allow_empty=True), allow_empty=True
    )

    def validate_table_columns(self, value):
        """
        Reject unknown collections, unknown columns and empty lists.

        Stricter than the user PATCH, which drops unknown keys because it
        round-trips stored settings from stale clients. The admin tab never
        sends an unknown key. An empty list would read as "0 columns" here
        while visitors fall back to the registry default.
        """
        cleaned, dropped = clean_table_columns(value)
        if dropped:
            reason = f"Unknown table column keys: {dropped}"
            raise ValidationError(reason)
        if empty := sorted(key for key, columns in cleaned.items() if not columns):
            reason = f"Choose at least one column for {empty}, or clear them."
            raise ValidationError(reason)
        return cleaned


class SettingsDefaultsReaderSerializer(Serializer):
    """Site default global reader settings."""

    fit_to = FitToField()
    reading_direction = ReadingDirectionField()
    two_pages = BooleanField()
    page_transition = BooleanField()
    cache_book = BooleanField()


def _flatten_errors(detail) -> Any:
    """Lift the browser / reader section errors to one flat field map."""
    if not isinstance(detail, Mapping):
        return detail
    flat: dict[str, Any] = {}
    for key, value in detail.items():
        if key in ("browser", "reader") and isinstance(value, Mapping):
            flat.update(value)
        else:
            flat[key] = value
    return flat


class SettingsDefaultsSerializer(Serializer):
    """
    Serializer for the SettingsDefaults singleton.

    The wire nests the columns in ``browser`` and ``reader`` sections.
    Validation runs against the merged instance plus the new values, since
    the PUT is partial, and is strict: stored settings rows are never
    re-validated and the SPA echoes every setting through strict
    ChoiceFields, so an incoherent default would 400 every browse.
    """

    browser = SettingsDefaultsBrowserSerializer(source="*", required=False)
    reader = SettingsDefaultsReaderSerializer(source="*", required=False)

    def _merged(self, attrs: Mapping, key: str) -> Any:
        """Return the incoming value, else the stored one."""
        if key in attrs:
            return attrs[key]
        return getattr(self.instance, key)

    def _validate_top_collection(self, attrs: Mapping) -> None:
        """Rule 1: the top collection must be reachable with these show flags."""
        top_collection = self._merged(attrs, "top_collection")
        show = {c: self._merged(attrs, f"show_{c}") for c in SHOW_COLLECTIONS}
        folder_view = folder_view_on()
        if top_collection == coherent_top_collection(
            top_collection, show, folder_view=folder_view
        ):
            return
        label = BROWSER_TOP_COLLECTION_CHOICES.get(top_collection, top_collection)
        if top_collection == "folders":
            reason = (
                "Folders can't be the top collection while Folder View is off "
                "on the Settings tab."
            )
        else:
            reason = f"{label} can't be the top collection while Show {label} is off."
        raise ValidationError({"top_collection": reason})

    def _validate_two_pages(self, attrs: Mapping) -> None:
        """Rule 2: two pages is a horizontal reading mode."""
        two_pages = self._merged(attrs, "two_pages")
        direction = self._merged(attrs, "reading_direction")
        if two_pages and direction in _VERTICAL_READING_DIRECTIONS:
            reason = "Two pages can't be on with a vertical reading direction."
            raise ValidationError({"two_pages": reason})

    @override
    def to_internal_value(self, data):
        """Report section errors as one flat field map for the admin form."""
        try:
            return super().to_internal_value(data)
        except ValidationError as exc:
            raise ValidationError(_flatten_errors(exc.detail)) from exc

    @override
    def validate(self, attrs):
        """Check the merged settings are coherent."""
        self._validate_top_collection(attrs)
        self._validate_two_pages(attrs)
        return attrs

    @override
    def update(self, instance: SettingsDefaults, validated_data) -> SettingsDefaults:
        """Write the changed columns onto the singleton."""
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
