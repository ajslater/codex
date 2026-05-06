"""Browser Page Serializer."""

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
from codex.serializers.fields.group import BrowseGroupField
from codex.views.browser.columns import m2m_alias_for, m2m_columns


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

    group_name = CharField(read_only=True)
    group_number_to = CharField(read_only=True)
    group_count = IntegerField(read_only=True, allow_null=True)


def _row_repr(instance, columns: tuple[str, ...]) -> dict:
    """Project a queryset row to the per-row dict for table view."""
    # ``pk``, ``group``, and ``ids`` are always emitted regardless of
    # the user's column selection. They're routing metadata: ``group``
    # tells the frontend whether the row is a Comic or a group node,
    # and ``ids`` is the list of pks the next route should target.
    # Without these, clicking a Publisher row would route to a comic
    # whose id matches the publisher's pk.
    row: dict = {
        "pk": instance.pk,
        "group": getattr(instance, "group", None),
        "ids": getattr(instance, "ids", None),
    }
    m2m_keys = m2m_columns()
    for col in columns:
        if col in ("pk", "group", "ids"):
            continue
        if col == "cover":
            row["cover_pk"] = getattr(instance, "cover_pk", None) or instance.pk
            row["cover_custom_pk"] = getattr(instance, "cover_custom_pk", None)
            continue
        if col in m2m_keys:
            # M2M aggregates live under a prefixed alias (the unprefixed
            # name would clash with the model's M2M field attribute).
            row[col] = getattr(instance, m2m_alias_for(col), None)
            continue
        # ``getattr`` covers direct fields, F-expression annotations
        # (publisher_name etc.), and aggregates added downstream.
        # Columns whose value source isn't annotated yet return None;
        # the frontend renders them as empty cells.
        row[col] = getattr(instance, col, None)
    return row


class BrowserPageSerializer(Serializer):
    """
    The main browse list.

    Always emits the cards-shape (``groups`` / ``books``). Also emits
    a ``rows`` list projected through the requested ``columns`` when
    the caller sets ``columns`` on the data dict (table-view mode).
    The dual emission lets the frontend's mobile-auto-fallback render
    the card grid on narrow viewports even when the user has table
    view enabled — the card data is already in the response.
    """

    admin_flags = BrowserAdminFlagsSerializer(read_only=True)
    breadcrumbs = BreadcrumbsField(read_only=True)
    title = BrowserTitleSerializer(read_only=True)
    zero_pad = IntegerField(read_only=True)
    libraries_exist = BooleanField(read_only=True)
    model_group = BrowseGroupField(read_only=True)
    num_pages = IntegerField(read_only=True)
    groups = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    books = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    rows = SerializerMethodField()
    fts = BooleanField(read_only=True)
    search_error = CharField(read_only=True)
    mtime = TimestampField(read_only=True)

    def get_rows(self, obj) -> list:
        """Project groups + books through ``columns`` if requested."""
        columns = obj.get("columns") if isinstance(obj, dict) else None
        if not columns:
            return []
        columns = tuple(columns)
        groups = obj.get("groups", ()) or ()
        books = obj.get("books", ()) or ()
        return [_row_repr(item, columns) for item in (*groups, *books)]
