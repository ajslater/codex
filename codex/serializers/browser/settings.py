"""Serializers for the browser view."""

from typing import override

from loguru import logger
from rest_framework.serializers import (
    BooleanField,
    CharField,
    ChoiceField,
    DictField,
    IntegerField,
    ListField,
    Serializer,
    ValidationError,
)

from codex.choices.browser import (
    BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS,
    BROWSER_ORDER_BY_CHOICES,
    BROWSER_TABLE_COLUMNS,
    BROWSER_TABLE_COVER_SIZE_CHOICES,
    BROWSER_TOP_COLLECTION_CHOICES,
    BROWSER_VIEW_MODE_CHOICES,
)
from codex.serializers.browser.filters import BrowserSettingsFilterInputSerializer
from codex.serializers.fields import TimestampField
from codex.serializers.fields.collection import (
    BrowseCollectionField,
    BrowserRouteCollectionField,
)
from codex.serializers.mixins import JSONFieldSerializer
from codex.serializers.route import SimpleRouteSerializer
from codex.serializers.settings import SettingsInputSerializer

# Sorts worth remembering per top collection. ``search_score`` only means
# anything while a search is running, so it never enters the memory.
_MEMORABLE_ORDER_BY_KEYS = frozenset(BROWSER_ORDER_BY_CHOICES.keys()) - {"search_score"}
# Extra (secondary) sort keys the order pipeline can resolve anywhere.
_MEMORABLE_EXTRA_KEYS = (
    frozenset(BROWSER_ORDER_BY_CHOICES.keys()) - BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS
)


def _clean_remembered_extra_keys(value) -> list[dict]:
    """Keep the well formed, sortable, non duplicate extra sort entries."""
    cleaned: list[dict] = []
    if not isinstance(value, list | tuple):
        return cleaned
    seen: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key not in _MEMORABLE_EXTRA_KEYS or key in seen:
            continue
        seen.add(key)
        cleaned.append({"key": key, "reverse": bool(entry.get("reverse", False))})
    return cleaned


def _clean_remembered_order(value) -> dict | None:
    """Coerce one remembered sort, or None when it can't be salvaged."""
    if not isinstance(value, dict):
        return None
    order_by = value.get("order_by")
    if order_by not in _MEMORABLE_ORDER_BY_KEYS:
        return None
    return {
        "order_by": order_by,
        "order_reverse": bool(value.get("order_reverse", False)),
        "order_extra_keys": _clean_remembered_extra_keys(value.get("order_extra_keys")),
    }


class BrowserSettingsShowCollectionFlagsSerializer(Serializer):
    """Show Collection Flags (collection vocabulary)."""

    publishers = BooleanField()
    imprints = BooleanField()
    series = BooleanField()
    volumes = BooleanField()


class BrowserSettingsLastRouteSerializer(Serializer):
    """Last route for browser settings output."""

    collection = CharField()
    pks = CharField()
    page = IntegerField()

    @override
    def to_representation(self, instance) -> dict:
        """Handle both dicts and SettingsBrowserLastRoute model instances."""
        if not isinstance(instance, dict):
            # Model instance
            pks = instance.pks
            instance = {
                "collection": instance.collection,
                "pks": tuple(pks) if pks else (0,),
                "page": instance.page,
            }
        return instance


class BrowserFilterChoicesInputSerializer(JSONFieldSerializer):
    """Browser Settings for the filter choices response."""

    JSON_FIELDS: frozenset[str] = frozenset({"filters"})

    filters = BrowserSettingsFilterInputSerializer(required=False)
    # NOT Sanitized because so complex.
    search = CharField(allow_blank=True, required=False)


class BrowserCoverInputSerializerBase(BrowserFilterChoicesInputSerializer):
    """Base Serializer for Cover and Settings."""

    JSON_FIELDS = frozenset(BrowserFilterChoicesInputSerializer.JSON_FIELDS | {"show"})

    custom_covers = BooleanField(required=False)
    dynamic_covers = BooleanField(required=False)
    order_by = ChoiceField(
        choices=tuple(BROWSER_ORDER_BY_CHOICES.keys()), required=False
    )
    order_reverse = BooleanField(required=False)
    show = BrowserSettingsShowCollectionFlagsSerializer(required=False)


class BrowserCoverInputSerializer(BrowserCoverInputSerializerBase):
    """Browser Settings for the cover response."""

    JSON_FIELDS = frozenset(
        BrowserCoverInputSerializerBase.JSON_FIELDS | {"parent_route"}
    )

    parent_route = SimpleRouteSerializer(required=False)


class BrowserSettingsSerializerBase(BrowserCoverInputSerializerBase):
    """Base Serializer for Browser & OPDS Settings."""

    top_collection = BrowseCollectionField(required=False)

    @override
    def to_internal_value(self, data) -> dict:
        if "search" not in data and (search := data.get("query", data.get("q"))):
            # Accept "query" or "q" as an alias for "search".
            data = data.copy()
            data["search"] = search
        return super().to_internal_value(data)


class OPDSSettingsSerializer(BrowserSettingsSerializerBase):
    """Browser Settings for the OPDS."""

    limit = IntegerField(required=False)
    opds_metadata = BooleanField(required=False)
    query = CharField(allow_blank=True, required=False)  # OPDS 2.0


class BrowserSettingsSerializer(BrowserSettingsSerializerBase):
    """
    Browser Settings that the user can change.

    This is the only browse serializer that's submitted.
    """

    JSON_FIELDS = frozenset(
        BrowserSettingsSerializerBase.JSON_FIELDS
        | {"table_columns", "order_extra_keys", "collection_order_memory"}
    )

    mtime = TimestampField(read_only=True)
    twenty_four_hour_time = BooleanField(required=False)
    always_show_filename = BooleanField(required=False)
    view_mode = ChoiceField(
        choices=tuple(BROWSER_VIEW_MODE_CHOICES.keys()), required=False
    )
    table_columns = DictField(
        child=ListField(child=CharField(), allow_empty=True),
        required=False,
        allow_empty=True,
    )
    table_cover_size = ChoiceField(
        choices=tuple(BROWSER_TABLE_COVER_SIZE_CHOICES.keys()), required=False
    )
    # Multi-column sort: list of secondary sort entries appended to
    # the primary ``order_by`` ORDER BY. Each child is a dict
    # ``{"key": <order_by enum>, "reverse": <bool>}``. Validated in
    # ``validate_order_extra_keys`` against the order_by enum and
    # de-duped against the primary key.
    order_extra_keys = ListField(
        child=DictField(),
        required=False,
        allow_empty=True,
    )
    # The sort each top collection was last browsed with, keyed by
    # top_collection. Cleaned in ``validate_collection_order_memory``;
    # see the model field for the stored shape.
    collection_order_memory = DictField(
        child=DictField(),
        required=False,
        allow_empty=True,
    )

    def validate_table_columns(self, value):
        """
        Drop unknown top-collection keys and unknown column keys.

        ``table_columns`` is round-tripped from stored settings, so a stale or
        partially-migrated client must not hard-400 the entire browse page.
        Unknown top-collection keys (e.g. legacy single-char group codes) and
        unknown column keys are dropped with a warning rather than raising.
        """
        valid_top_collections = set(BROWSER_TOP_COLLECTION_CHOICES.keys())
        valid_columns = set(BROWSER_TABLE_COLUMNS.keys())
        cleaned: dict[str, list[str]] = {}
        for top_collection, columns in value.items():
            if top_collection not in valid_top_collections:
                logger.warning(
                    f"Dropping unknown table_columns top_collection {top_collection!r}"
                )
                continue
            invalid_columns = set(columns) - valid_columns
            if invalid_columns:
                msg = (
                    f"Dropping unknown table_columns columns for "
                    f"{top_collection!r}: {sorted(invalid_columns)}"
                )
                logger.warning(msg)
            cleaned[top_collection] = [c for c in columns if c in valid_columns]
        return cleaned

    def validate_collection_order_memory(self, value):
        """
        Drop unknown top collections and unusable remembered sorts.

        Like ``table_columns`` this round-trips out of stored settings, so a
        stale client must not hard-400 the whole browse page. An entry naming
        a sort that no longer exists is dropped with a warning; the collection
        then just keeps whatever sort it is browsed with next.
        """
        cleaned: dict[str, dict] = {}
        for top_collection, order in value.items():
            if top_collection not in BROWSER_TOP_COLLECTION_CHOICES:
                msg = (
                    f"Dropping unknown collection_order_memory top_collection "
                    f"{top_collection!r}"
                )
                logger.warning(msg)
                continue
            remembered_order = _clean_remembered_order(order)
            if remembered_order is None:
                msg = (
                    f"Dropping unusable collection_order_memory order for "
                    f"{top_collection!r}"
                )
                logger.warning(msg)
                continue
            cleaned[top_collection] = remembered_order
        return cleaned

    def validate_order_extra_keys(self, value):
        """
        Reject malformed entries; coerce to the canonical shape.

        Drops duplicate keys (first occurrence wins) and any entry
        whose ``key`` is not a known order_by enum value. ``reverse``
        coerces to bool. The primary ``order_by`` isn't filtered out
        here — the caller may swap primaries and we shouldn't lose
        the entry on the way through; the order pipeline tolerates
        a duplicate sort column (redundant ORDER BY).
        """
        valid_keys = set(BROWSER_ORDER_BY_CHOICES.keys())
        seen: set[str] = set()
        out: list[dict] = []
        for entry in value:
            if not isinstance(entry, dict):
                reason = f"order_extra_keys entries must be dicts, got {entry!r}"
                raise ValidationError(reason)
            key = entry.get("key")
            if not isinstance(key, str) or key not in valid_keys:
                reason = f"Invalid order_extra_keys key: {key!r}"
                raise ValidationError(reason)
            if key in seen:
                continue
            seen.add(key)
            out.append({"key": key, "reverse": bool(entry.get("reverse", False))})
        return out


class BrowserSettingsInputSerializer(SettingsInputSerializer):
    """Browser Set Settings Input Serializer."""

    collection = BrowserRouteCollectionField(required=False)


class BrowserPageInputSerializer(BrowserSettingsSerializer):
    """
    Input parser for the browse page endpoint.

    Adds the ``columns`` query param: a comma-separated list of column
    keys from the table-view registry. The browser view consumes it
    when ``view_mode == "table"`` to project rows. Each key must be a
    valid registry entry; unknown keys cause a 400.
    """

    columns = CharField(required=False, allow_blank=True)

    def validate_columns(self, value: str) -> tuple[str, ...]:
        """Split, trim, and validate column keys against the registry."""
        if not value:
            return ()
        keys = tuple(k.strip() for k in value.split(",") if k.strip())
        valid = set(BROWSER_TABLE_COLUMNS.keys())
        invalid = [k for k in keys if k not in valid]
        if invalid:
            reason = f"Invalid column keys: {sorted(invalid)}"
            raise ValidationError(reason)
        return keys
