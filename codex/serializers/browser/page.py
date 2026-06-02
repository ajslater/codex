"""Browser Page Serializer."""

from typing import override

import pycountry
from rest_framework.fields import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
    SerializerMethodField,
)
from rest_framework.serializers import Serializer

from codex.serializers.browser.mixins import (
    BrowserAggregateSerializerMixin,
)
from codex.serializers.fields import TimestampField
from codex.serializers.fields.browser import BreadcrumbsField
from codex.serializers.fields.collection import BrowseCollectionField
from codex.views.browser.columns import (
    fk_alias_for,
    fk_name_columns,
    m2m_alias_for,
    m2m_columns,
)


def _resolve_country(code) -> str | None:
    """Translate ISO-3166 alpha-2 country codes to readable names."""
    if not code:
        return None
    record = pycountry.countries.get(alpha_2=str(code).upper())
    return record.name if record else str(code)


def _format_issue_number(number) -> str:
    """
    Format the numeric part of the compound issue column.

    Trims trailing zeros after the decimal so a Decimal "1.00" reads
    "1" and "1.50" reads "1.5". Returns "" when number is missing.
    """
    if number is None:
        return ""
    s = str(number)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _format_issue(number, suffix) -> dict:
    """
    Render the compound ``issue`` column as ``{number, suffix}``.

    Both halves stay separate on the wire so the table-view cell can
    render the number right-justified and the suffix left-justified —
    digits in a column then align at the boundary regardless of
    suffix presence (1, 2a, 100, 25.5b all line up by the number's
    right edge).
    """
    return {
        "number": _format_issue_number(number),
        "suffix": suffix or "",
    }


def _resolve_language(code) -> str | None:
    """Translate ISO-639 alpha-2 language codes to readable names."""
    if not code:
        return None
    record = pycountry.languages.get(alpha_2=str(code).lower())
    return record.name if record else str(code)


# Per-column display transforms applied to the raw queryset value
# before it lands on the wire. Each callable takes the raw value
# (typically a string from an FK annotation) and returns the display
# string. The Country / Language tables store ISO-2 codes in their
# ``name`` field, so the column lookup hits pycountry to surface the
# full readable name.
_COLUMN_VALUE_TRANSFORMS = {
    "country": _resolve_country,
    "language": _resolve_language,
}

# Routing metadata that ``_row_repr`` always emits regardless of the
# user's column selection. Skipped during the per-column dispatch loop
# because the values are pre-populated on the row dict.
_ROUTING_COLUMNS = frozenset({"pk", "collection", "ids"})


def _apply_transform(col: str, value):
    """Run the per-column display transform if the column has one."""
    transform = _COLUMN_VALUE_TRANSFORMS.get(col)
    return transform(value) if transform else value


class BrowserCardSerializer(BrowserAggregateSerializerMixin, Serializer):
    """Browse card displayed in the browser."""

    pk = IntegerField(read_only=True)
    publisher_name = CharField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    volume_number_to = CharField(read_only=True)
    file_name = CharField(read_only=True)
    name = CharField(read_only=True)
    number_to = CharField(read_only=True)
    issue_number = DecimalField(
        max_digits=16,
        decimal_places=3,
        read_only=True,
        coerce_to_string=False,
    )
    issue_suffix = CharField(read_only=True)
    order_value = CharField(read_only=True)
    page_count = IntegerField(read_only=True)
    reading_direction = CharField(read_only=True)
    has_metadata = BooleanField(read_only=True)
    # cover_pk and cover_custom_pk are pre-computed on group cards by
    # BrowserAnnotateCoverView. Comic book cards lack the annotations; the
    # method fields fall back to ``obj.pk`` so the frontend can build a
    # uniform ``/c/<pk>/cover.webp`` URL without a per-card branch.
    cover_pk = SerializerMethodField(read_only=True)
    cover_custom_pk = SerializerMethodField(read_only=True)

    def get_cover_pk(self, obj) -> int:
        """Return pre-computed cover pk, falling back to the card's own pk."""
        value = getattr(obj, "cover_pk", None)
        return value if value is not None else obj.pk

    def get_cover_custom_pk(self, obj) -> int | None:
        """Return the custom cover pk when present, else None."""
        return getattr(obj, "cover_custom_pk", None)


class BrowserAdminFlagsSerializer(Serializer):
    """These choices change with browse context."""

    folder_view = BooleanField(read_only=True)
    import_metadata = BooleanField(read_only=True)


class BrowserTitleSerializer(Serializer):
    """Elements for constructing the browse title."""

    collection_name = CharField(read_only=True)
    collection_number_to = CharField(read_only=True)
    collection_count = IntegerField(read_only=True, allow_null=True)


def _emit_cover(row, instance) -> None:
    """Populate the cover_pk / cover_custom_pk pair from a single ``cover`` request."""
    row["cover_pk"] = getattr(instance, "cover_pk", None) or instance.pk
    row["cover_custom_pk"] = getattr(instance, "cover_custom_pk", None)


def _emit_issue(row, instance) -> None:
    """Render the compound issue column as ``{number, suffix}`` on the row."""
    # Compound from issue_number + issue_suffix on the Comic, emitted as
    # ``{number, suffix}`` so the cell can split-justify the halves.
    # Group rows yield empty strings for both (intersection of distinct
    # issues across child comics is rarely meaningful).
    row["issue"] = _format_issue(
        getattr(instance, "issue_number", None),
        getattr(instance, "issue_suffix", "") or "",
    )


def _emit_column(
    row,
    instance,
    col: str,
    row_intersections: dict,
    m2m_keys: frozenset[str],
    fk_keys: frozenset[str],
) -> None:
    """
    Resolve and emit a single column's value onto ``row``.

    Lookup order: special-case (cover / issue) → group-row intersection
    (with country / language transform) → M2M annotation alias → FK-name
    annotation alias (with transform) → direct attribute lookup. M2M and
    FK-name aliases are prefixed because the unprefixed name collides
    with the matching Comic field attribute.
    """
    if col == "cover":
        _emit_cover(row, instance)
    elif col == "issue":
        _emit_issue(row, instance)
    elif col in row_intersections:
        # Group-row intersection takes precedence (and applies country /
        # language transforms the same way the FK-alias path does).
        row[col] = _apply_transform(col, row_intersections[col])
    elif col in m2m_keys:
        row[col] = getattr(instance, m2m_alias_for(col), None)
    elif col in fk_keys:
        row[col] = _apply_transform(col, getattr(instance, fk_alias_for(col), None))
    else:
        # ``getattr`` covers direct fields, F-expression annotations
        # (publisher_name etc.), and aggregates added downstream.
        # Columns whose value source isn't annotated yet return None;
        # the frontend renders them as empty cells.
        row[col] = getattr(instance, col, None)


def _row_repr(
    instance, columns: tuple[str, ...], intersections: dict | None = None
) -> dict:
    """
    Project a queryset row to the per-row dict for table view.

    For Comic rows, values come from the queryset annotations / direct
    fields. For group rows (Series, Publisher, etc.), the optional
    ``intersections`` dict carries per-row intersections of child-comic
    values: M2M values shared by every child comic, scalars where every
    child comic has the same value. When present, intersections take
    precedence over direct attribute lookups for the columns they cover.
    """
    # ``pk``, ``collection``, and ``ids`` are always emitted regardless
    # of the user's column selection. They're routing metadata:
    # ``collection`` tells the frontend whether the row is a Comic or a
    # collection node, and ``ids`` is the list of pks the next route
    # should target. (The value comes from the ``nav_collection``
    # annotation, an internal alias the OPDS entry path also reads.)
    # Without these, clicking a Publisher row would route to a comic
    # whose id matches the publisher's pk.
    row: dict = {
        "pk": instance.pk,
        "collection": getattr(instance, "nav_collection", None),
        "ids": getattr(instance, "ids", None),
    }
    m2m_keys = m2m_columns()
    fk_keys = fk_name_columns()
    row_intersections = (
        intersections.get(instance.pk) if intersections else None
    ) or {}
    for col in columns:
        if col in _ROUTING_COLUMNS:
            continue
        _emit_column(row, instance, col, row_intersections, m2m_keys, fk_keys)
    return row


class BrowserPageSerializer(Serializer):
    """
    The main browse list.

    Mode-aware: table-mode responses emit ``rows`` (no ``collections``/
    ``books``) and card-mode responses emit ``collections``/``books`` (no
    ``rows``). The active view mode is inferred from the presence of
    ``columns`` on the payload (``BrowserView`` only populates them
    when ``view_mode == "table"``).
    """

    admin_flags = BrowserAdminFlagsSerializer(read_only=True)
    breadcrumbs = BreadcrumbsField(read_only=True)
    title = BrowserTitleSerializer(read_only=True)
    zero_pad = IntegerField(read_only=True)
    libraries_exist = BooleanField(read_only=True)
    model_collection = BrowseCollectionField(read_only=True)
    num_pages = IntegerField(read_only=True)
    collections = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    books = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    rows = SerializerMethodField()
    fts = BooleanField(read_only=True)
    search_error = CharField(read_only=True)
    mtime = TimestampField(read_only=True)

    def get_rows(self, obj) -> list:
        """Project collections + books through ``columns`` if requested."""
        columns = obj.get("columns") if isinstance(obj, dict) else None
        if not columns:
            return []
        columns = tuple(columns)
        collections = obj.get("collections", ()) or ()
        books = obj.get("books", ()) or ()
        intersections = obj.get("group_intersections") or None
        return [
            _row_repr(item, columns, intersections=intersections)
            for item in (*collections, *books)
        ]

    @override
    def to_representation(self, instance):
        """
        Strip the unused mode's fields after the base projection.

        Table mode: ``rows`` carries every projected column; the card
        fields are noise and the largest part of the payload.
        Card mode: ``rows`` is empty unless columns were requested,
        so drop the always-empty ``rows`` slot.
        """
        data = super().to_representation(instance)
        if self._view_mode(instance) == "table":
            data.pop("collections", None)
            data.pop("books", None)
        else:
            data.pop("rows", None)
        return data

    @staticmethod
    def _view_mode(instance) -> str:
        """
        Resolve the active view mode from the response payload.

        The instance dict carries ``columns`` only when the request
        asked for table-mode (``BrowserView`` populates ``columns``
        from the user settings only when ``view_mode == "table"``).
        That gives a reliable, response-payload-local signal without
        threading view_mode through every intermediate.
        """
        if not isinstance(instance, dict):
            return "cover"
        columns = instance.get("columns")
        return "table" if columns else "cover"
