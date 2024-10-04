"""Browser Page Serializer."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DecimalField,
    IntegerField,
    Serializer,
)

from codex.serializers.browser.mixins import (
    BrowserAggregateSerializerMixin,
)
from codex.serializers.fields import BreadcrumbsField, TimestampField


class BrowserCardSerializer(BrowserAggregateSerializerMixin):
    """Browse card displayed in the browser."""

    pk = IntegerField(read_only=True)
    publisher_name = CharField(read_only=True)
    series_name = CharField(read_only=True)
    volume_name = CharField(read_only=True)
    name = CharField(read_only=True)
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


class BrowserAdminFlagsSerializer(Serializer):
    """These choices change with browse context."""

    folder_view = BooleanField(read_only=True)
    import_metadata = BooleanField(read_only=True)


class BrowserTitleSerializer(Serializer):
    """Elements for constructing the browse title."""

    group_name = CharField(read_only=True)
    group_count = IntegerField(read_only=True, allow_null=True)


class BrowserPageSerializer(Serializer):
    """The main browse list."""

    admin_flags = BrowserAdminFlagsSerializer(read_only=True)
    breadcrumbs = BreadcrumbsField(read_only=True)
    title = BrowserTitleSerializer(read_only=True)
    zero_pad = IntegerField(read_only=True)
    libraries_exist = BooleanField(read_only=True)
    model_group = CharField(read_only=True)
    num_pages = IntegerField(read_only=True)
    groups = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    books = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    fts = BooleanField(read_only=True)
    search_error = CharField(read_only=True)
    mtime = TimestampField(read_only=True)
