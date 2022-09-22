"""View for marking comics read and unread."""
from copy import copy

from django.db.models import Count, F, IntegerField, Subquery, Value
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.models import AdminFlag, Comic
from codex.serializers.metadata import (
    METADATA_ORDERED_UNIONFIX_VALUES_MAP,
    MetadataSerializer,
)
from codex.settings.logging import get_logger
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.browser_metadata_base import BrowserMetadataBaseView


LOG = get_logger(__name__)


class MetadataView(BrowserMetadataBaseView):
    """Comic metadata."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = MetadataSerializer

    # DO NOT USE BY ITSELF. USE _get_comic_value_fields() instead.
    _COMIC_VALUE_FIELDS = set(
        (
            "age_rating",
            "comments",
            "community_rating",
            "country",
            "critical_rating",
            "day",
            "file_format",
            "format",
            "issue",
            "issue_suffix",
            "language",
            "month",
            "notes",
            "read_ltr",
            "scan_info",
            "summary",
            "web",
            "year",
        )
    )
    _ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS = set(("path",))
    _COMIC_VALUE_FIELDS_CONFLICTING = set(
        (
            "name",
            "updated_at",
            "created_at",
        )
    )
    _COMIC_VALUE_FIELDS_CONFLICTING_PREFIX = "conflict_"
    _COMIC_FK_FIELDS = set(
        (
            "publisher",
            "imprint",
            "series",
            "volume",
        )
    )
    _COMIC_FK_FIELDS_MAP = {
        "f": _COMIC_FK_FIELDS,
        "p": _COMIC_FK_FIELDS.difference(frozenset(["publisher"])),
        "i": _COMIC_FK_FIELDS.difference(frozenset(["imprint"])),
        "s": _COMIC_FK_FIELDS.difference(frozenset(["series"])),
        "v": _COMIC_FK_FIELDS.difference(frozenset(["volume"])),
        "c": _COMIC_FK_FIELDS,
    }
    _COMIC_FK_ANNOTATION_PREFIX = "fk_"
    _COMIC_RELATED_VALUE_FIELDS = set(("series__volume_count", "volume__issue_count"))
    _COUNT_FIELD_MAP = {
        "imprint": ("volume_count", "fk_series_volume_count"),
        "series": ("issue_count", "fk_volume_issue_count"),
    }
    _COMIC_M2M_FIELDS = set(
        (
            "characters",
            "credits",
            "genres",
            "locations",
            "series_groups",
            "story_arcs",
            "tags",
            "teams",
        )
    )
    _PATH_GROUPS = ("c", "f")
    _CREDIT_RELATIONS = ("role", "person")

    def _get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = copy(self._COMIC_VALUE_FIELDS)
        is_not_path_group = self.group not in self._PATH_GROUPS
        if (self._is_enabled_folder_view() or self.is_admin()) and is_not_path_group:
            fields |= self._ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
        return fields

    def _intersection_annotate(
        self,
        simple_qs,
        qs,
        fields,
        related_suffix="",
        annotation_prefix="",
    ):
        """Annotate the intersection of value and fk fields."""
        for field in fields:
            # Annotate variant counts
            # Have to use simple_qs because every annotation in the loop
            # corrupts the the main qs
            # If 1 variant, annotate value, otherwise None
            if self.is_model_comic:
                full_field = field
            else:
                full_field = "comic__" + field

            sq = (
                simple_qs.values("id")
                .order_by()  # just in case
                .annotate(count=Count(full_field, distinct=True))
                .filter(count=1)
                .values_list(full_field + related_suffix, flat=True)
            )

            # The subquery above would work without this python dual evaluation
            # if we could group by only model.id. However, the SQL standard and
            # therefore Django, states that anything selected must be grouped by,
            # which leads to multiple query results instead of null or one result.
            # The query only version of this from 0.9.14 worked in most cases, but
            # fractured on the language tag for some reason.
            if len(sq) != 1:
                val = Value(None, IntegerField())
            else:
                val = Subquery(sq)

            ann_field = (annotation_prefix + field).replace("__", "_")
            qs = qs.annotate(**{ann_field: val})

        return qs

    @classmethod
    def _field_copy_fk_count(cls, field_name, obj, val):
        """Copy those pesky fk count fields from annotations."""
        op_field_names = cls._COUNT_FIELD_MAP.get(field_name)
        if not op_field_names:
            return
        count_field, count_src_field_name = op_field_names
        val[count_field] = obj[count_src_field_name]

    @classmethod
    def _field_copy(cls, obj, fields, prefix, fk_field=None):
        """Copy annotation fields into comic type fields."""
        for field_name in fields:
            src_field_name = f"{prefix}{field_name}"
            val = obj[src_field_name]
            if fk_field:
                val = {fk_field: val}
                # Add special count fields
                cls._field_copy_fk_count(field_name, obj, val)
            obj[field_name] = val

    def _annotate_aggregates(self, qs):
        """Annotate aggregate values."""
        if not self.is_model_comic:
            size_func = self.get_aggregate_func("size", self.is_model_comic)
            qs = qs.annotate(size=size_func)
        qs = self.annotate_common_aggregates(qs, self.model)
        return qs

    def _annotate_values_and_fks(self, qs, simple_qs):
        """Annotate comic values and comic foreign key values."""
        # Simple Values
        if not self.is_model_comic:
            comic_value_fields = self._get_comic_value_fields()
            qs = self._intersection_annotate(simple_qs, qs, comic_value_fields)

            # Conflicting Simple Values
            qs = self._intersection_annotate(
                simple_qs,
                qs,
                self._COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=self._COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )
        elif self.is_admin() or self._is_enabled_folder_view():
            qs = qs.annotate(library_path=F("library__path"))

        # Foreign Keys
        fk_fields = copy(self._COMIC_FK_FIELDS_MAP[self.group])
        qs = self._intersection_annotate(
            simple_qs,
            qs,
            fk_fields,
            related_suffix="__name",
            annotation_prefix=self._COMIC_FK_ANNOTATION_PREFIX,
        )

        # Foreign Keys with special count values
        qs = self._intersection_annotate(
            simple_qs,
            qs,
            self._COMIC_RELATED_VALUE_FIELDS,
            annotation_prefix=self._COMIC_FK_ANNOTATION_PREFIX,
        )
        return qs

    def _query_m2m_intersections(self, simple_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}
        if self.is_model_comic:
            pk_field = "pk"
        else:
            pk_field = "comic__pk"
        comic_pks = simple_qs.values_list(pk_field, flat=True)
        for field_name in self._COMIC_M2M_FIELDS:
            model = Comic._meta.get_field(field_name).related_model
            if not model:
                raise ValueError(f"No model found for comic field: {field_name}")

            intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
            if field_name == "credits":
                intersection_qs = intersection_qs.select_related(
                    *self._CREDIT_RELATIONS
                )
                values = self._CREDIT_RELATIONS
            else:
                values = ("name",)

            # order_by() is very important for grouping
            intersection_qs = (
                intersection_qs.only(*values)
                .annotate(count=Count("comic"))
                .order_by()
                .filter(count=comic_pks.count())
            )
            m2m_intersections[field_name] = intersection_qs
        return m2m_intersections

    def _copy_annotations_into_comic_fields(self, obj, m2m_intersections):
        """Copy a bunch of values that i couldn't fit cleanly in the main queryset."""
        if self.model is None:
            raise ValueError(f"Cannot get metadata for {self.group=}")
        group_field = self.model.__name__.lower()
        obj[group_field] = {"name": obj["name"]}
        comic_fk_fields = copy(self._COMIC_FK_FIELDS_MAP[self.group])
        self._field_copy(
            obj,
            comic_fk_fields,
            self._COMIC_FK_ANNOTATION_PREFIX,
            "name",
        )

        if not self.is_model_comic:
            # this must come after fk_fields copy because of name
            # for fk models
            self._field_copy(
                obj,
                self._COMIC_VALUE_FIELDS_CONFLICTING,
                self._COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )

        obj.update(m2m_intersections)

        # path security
        if not self.is_admin():
            if self._is_enabled_folder_view():
                library_path = obj.get("library_path")
                if library_path:
                    obj["path"] = obj["path"].removeprefix(library_path)
                else:
                    obj["path"] = ""
            else:
                obj["path"] = ""

        # For highlighting the current group
        obj["group"] = self.group

        # copy into unionfix fields for serializer
        for unionfix_field, field in METADATA_ORDERED_UNIONFIX_VALUES_MAP.items():
            obj[unionfix_field] = obj.get(field)

        return obj

    def get_object(self):
        """Create a comic-like object from the current browser group."""
        # Comic model goes through the same code path as groups because
        # values dicts don't copy relations to the serializer. The values
        # dict is necessary because of the folders view union in browser.py.

        if self.model is None:
            raise NotFound(detail=f"Cannot get metadata for {self.group=}")

        object_filter, _ = self.get_query_filters_without_group(self.is_model_comic)
        pk = self.kwargs["pk"]
        qs = self.model.objects.filter(object_filter, pk=pk)

        qs = self._annotate_aggregates(qs)
        simple_qs = qs

        qs = self._annotate_values_and_fks(qs, simple_qs)
        m2m_intersections = self._query_m2m_intersections(simple_qs)
        obj = qs.values()[0]
        if not obj:
            raise NotFound(detail=f"Metadata for {self.group}/{pk} not found")

        obj = self._copy_annotations_into_comic_fields(obj, m2m_intersections)
        return obj

    def _is_enabled_folder_view(self):
        if self._efv_flag is None:
            self._efv_flag = (
                AdminFlag.objects.only("on").get(name=AdminFlag.ENABLE_FOLDER_VIEW).on
            )
        return self._efv_flag

    def _validate(self):
        self.model = self.GROUP_MODEL_MAP[self.group]
        if self.model is None:
            raise NotFound(detail=f"Cannot get metadata for {self.group=}")
        self.is_model_comic = self.group == self.COMIC_GROUP

    @extend_schema(request=BrowserMetadataBaseView.input_serializer_class)
    def get(self, _request, *args, **kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        self._efv_flag = None
        self.parse_params()
        self.group = self.kwargs["group"]
        self._validate()

        obj = self.get_object()

        serializer = self.get_serializer(obj)
        return Response(serializer.data)
