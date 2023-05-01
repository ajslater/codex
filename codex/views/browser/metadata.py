"""View for marking comics read and unread."""
from copy import copy

from django.db.models import Count, F, IntegerField, Subquery, Value
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.comic_field_names import COMIC_M2M_FIELD_NAMES
from codex.models import AdminFlag, Comic
from codex.serializers.metadata import MetadataSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.browser_annotations import BrowserAnnotationsView


class MetadataView(BrowserAnnotationsView):
    """Comic metadata."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]
    serializer_class = MetadataSerializer

    # DO NOT USE BY ITSELF. USE _get_comic_value_fields() instead.
    _COMIC_VALUE_FIELDS = {
        "age_rating",
        "comments",
        "community_rating",
        "country",
        "critical_rating",
        "day",
        "file_type",
        "issue",
        "issue_suffix",
        "language",
        "month",
        "notes",
        "original_format",
        "read_ltr",
        "scan_info",
        "summary",
        "web",
        "year",
    }
    _ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS = {"path"}
    _COMIC_VALUE_FIELDS_CONFLICTING = {
        "name",
        "updated_at",
        "created_at",
    }
    _COMIC_VALUE_FIELDS_CONFLICTING_PREFIX = "conflict_"
    _COMIC_FK_FIELDS_MAP = {
        "p": "publisher",
        "i": "imprint",
        "s": "series",
        "v": "volume",
    }
    _COMIC_RELATED_VALUE_FIELDS = {"series__volume_count", "volume__issue_count"}
    _PATH_GROUPS = ("c", "f")
    _CREATOR_RELATIONS = ("role", "person")

    def _get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = copy(self._COMIC_VALUE_FIELDS)
        is_not_path_group = self.group not in self._PATH_GROUPS
        if (self._is_enabled_folder_view() or self.is_admin()) and is_not_path_group:
            fields |= self._ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
        return fields

    def _intersection_annotate(
        self,
        querysets,
        fields,
        related_suffix="",
        annotation_prefix="",
    ):
        """Annotate the intersection of value and fk fields."""
        (simple_qs, qs) = querysets
        for field in fields:
            # Annotate variant counts
            # Have to use simple_qs because every annotation in the loop
            # corrupts the the main qs
            # If 1 variant, annotate value, otherwise None
            full_field = field if self.is_model_comic else "comic__" + field

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
            val = Value(None, IntegerField()) if len(sq) != 1 else Subquery(sq)

            ann_field = (annotation_prefix + field).replace("__", "_")
            qs = qs.annotate(**{ann_field: val})

        return simple_qs, qs

    def _annotate_aggregates(self, qs):
        """Annotate aggregate values."""
        if not self.is_model_comic:
            size_func = self.get_aggregate_func("size")
            qs = qs.annotate(size=size_func)
        qs = self.annotate_common_aggregates(qs, self.model, {})
        return qs

    def _annotate_values_and_fks(self, qs, simple_qs):
        """Annotate comic values and comic foreign key values."""
        # Simple Values
        querysets = (simple_qs, qs)
        if not self.is_model_comic:
            comic_value_fields = self._get_comic_value_fields()
            querysets = self._intersection_annotate(querysets, comic_value_fields)

            # Conflicting Simple Values
            querysets = self._intersection_annotate(
                querysets,
                self._COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=self._COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )
        elif self.is_admin() or self._is_enabled_folder_view():
            qs = qs.annotate(library_path=F("library__path"))
            querysets = (simple_qs, qs)

        # Foreign Keys with special count values
        _, qs = self._intersection_annotate(
            querysets,
            self._COMIC_RELATED_VALUE_FIELDS,
        )
        return qs

    def _annotate_for_filename(self, qs):
        """Annotate for the filename function."""
        if not self.is_model_comic:
            return qs
        qs = qs.annotate(parent_folder_pk=F("parent_folder_id"))
        return qs.annotate(series_name=F("series__name"), volume_name=F("volume__name"))

    def _query_m2m_intersections(self, simple_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}
        pk_field = "pk" if self.is_model_comic else "comic__pk"
        comic_pks = simple_qs.values_list(pk_field, flat=True)
        for field_name in COMIC_M2M_FIELD_NAMES:
            model = Comic._meta.get_field(field_name).related_model
            if not model:
                reason = f"No model found for comic field: {field_name}"
                raise ValueError(reason)

            intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
            if field_name == "creators":
                intersection_qs = intersection_qs.select_related(
                    *self._CREATOR_RELATIONS
                )
                values = self._CREATOR_RELATIONS
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

    def _path_security(self, obj):
        """Secure filesystem information for acl situation."""
        if self.is_admin():
            return
        if self._is_enabled_folder_view():
            library_path = obj.get("library_path", "")
            obj.path = obj.path.removeprefix(library_path)
        else:
            obj.path = ""

    def _highlight_current_group(self, obj):
        """Values for highlighting the current group."""
        obj.group = self.group
        if not self.is_model_comic:
            # move the name of the group to the correct field
            group_field = self.model.__name__.lower()
            group_obj = {"pk": obj.pk, "name": obj.name}
            setattr(obj, group_field, group_obj)
            obj.name = None

    @staticmethod
    def _copy_m2m_intersections(obj, m2m_intersections):
        """Copy the m2m intersections into the object."""
        for key, value in m2m_intersections.items():
            if hasattr(obj, key):
                # db set objects use their special method
                getattr(obj, key).set(value)
            else:
                setattr(obj, key, value)

    @classmethod
    def _copy_conflicting_simple_fields(cls, obj):
        for field in cls._COMIC_VALUE_FIELDS_CONFLICTING:
            """Copy conflicting fields over naturral fields."""
            conflict_field = cls._COMIC_VALUE_FIELDS_CONFLICTING_PREFIX + field
            val = getattr(obj, conflict_field)
            setattr(obj, field, val)

    def _copy_annotations_into_comic_fields(self, obj, m2m_intersections):
        """Copy a bunch of values that i couldn't fit cleanly in the main queryset."""
        self._path_security(obj)
        self._highlight_current_group(obj)
        self._copy_m2m_intersections(obj, m2m_intersections)
        if not self.is_model_comic:
            self._copy_conflicting_simple_fields(obj)

        # filename
        if self.model == Comic:
            obj.filename = Comic.get_filename(obj)

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
        qs = self._annotate_for_filename(qs)

        try:
            obj = qs.first()
            if not obj:
                reason = "Empty obj"
                raise ValueError(reason)  # noqa TRY301
        except (IndexError, ValueError) as exc:
            raise NotFound(
                detail=f"Filtered metadata for {self.group}/{pk} not found"
            ) from exc

        m2m_intersections = self._query_m2m_intersections(simple_qs)
        obj = self._copy_annotations_into_comic_fields(obj, m2m_intersections)
        return obj

    def _is_enabled_folder_view(self):
        if self._efv_flag is None:
            self._efv_flag = (
                AdminFlag.objects.only("on")
                .get(key=AdminFlag.FlagChoices.FOLDER_VIEW.value)
                .on
            )
        return self._efv_flag

    def _validate(self):
        self.model = self.GROUP_MODEL_MAP[self.group]
        if self.model is None:
            raise NotFound(detail=f"Cannot get metadata for {self.group=}")
        self.is_model_comic = self.group == self.COMIC_GROUP

    @extend_schema(request=BrowserAnnotationsView.input_serializer_class)
    def get(self, *args, **kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        self._efv_flag = None
        self.parse_params()
        self.set_order_key()
        self.group = self.kwargs["group"]
        self._validate()

        obj = self.get_object()

        serializer = self.get_serializer(obj)
        return Response(serializer.data)
