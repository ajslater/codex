"""Browser Page Serializer."""

from rest_framework.serializers import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
    ListSerializer,
    Serializer,
)

from codex.serializers.browser.mixins import (
    BrowserAggregateSerializerMixin,
)


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
    mtime = DateTimeField(format="%s", read_only=True)


class BrowserRouteSerializer(Serializer):
    """A vue route for the browser."""

    group = CharField(read_only=True)
    pks = CharField(read_only=True)
    page = IntegerField(read_only=True)
    name = CharField(read_only=True)

    def to_representation(self, instance):
        """Allow submission of sequences instead of strings for pks."""
        pks = instance.get("pks")
        if not pks:
            instance["pks"] = "0"
        elif not isinstance(pks, str):
            instance["pks"] = ",".join(str(pk) for pk in sorted(pks))
        return super().to_representation(instance)

    def to_internal_value(self, data):
        """Convert pk strings to tuples."""
        instance = super().to_internal_value(data)
        try:
            pks = instance.get("pks")
            if not pks:
                instance["pks"] = ()
            elif isinstance(pks, str):
                pks = tuple(sorted(int(pk) for pk in pks.split(",")))
                if 0 in pks:
                    pks = ()
                instance["pks"] = pks
        except ValueError:
            instance["pks"] = ()
        return instance


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
    breadcrumbs = ListSerializer(child=BrowserRouteSerializer())
    title = BrowserTitleSerializer(read_only=True)
    covers_timestamp = IntegerField(read_only=True)
    zero_pad = IntegerField(read_only=True)
    libraries_exist = BooleanField(read_only=True)
    model_group = CharField(read_only=True)
    num_pages = IntegerField(read_only=True)
    groups = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
    books = BrowserCardSerializer(allow_empty=True, read_only=True, many=True)
