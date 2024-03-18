"""View for marking comics read and unread."""

from typing import ClassVar

from django.db.models import Count, F, IntegerField, Subquery, Value
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.librarian.importer.const import COMIC_M2M_FIELD_NAMES
from codex.logger.logging import get_logger
from codex.models import AdminFlag, Comic
from codex.serializers.metadata import MetadataSerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.browser_annotations import BrowserAnnotationsView

LOG = get_logger(__name__)
_ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS = frozenset({"path"})
_COMIC_VALUE_FIELDS_CONFLICTING = frozenset(
    {
        "created_at",
        "name",
        "path",
        "updated_at",
    }
)
_DISABLED_VALUE_FIELD_NAMES = frozenset(
    {"id", "pk", "stat"} | _COMIC_VALUE_FIELDS_CONFLICTING
)
_COMIC_VALUE_FIELD_NAMES = frozenset(
    # contains path
    field.name
    for field in Comic._meta.get_fields()
    if not field.is_relation and field.name not in _DISABLED_VALUE_FIELD_NAMES
)
_COMIC_VALUE_FIELDS_CONFLICTING_PREFIX = "conflict_"
_COMIC_RELATED_VALUE_FIELDS = frozenset({"series__volume_count", "volume__issue_count"})
_PATH_GROUPS = ("c", "f")
_CONTRIBUTOR_RELATIONS = ("role", "person")


class MetadataView(BrowserAnnotationsView):
    """Comic metadata."""

    permission_classes: ClassVar[list] = [IsAuthenticatedOrEnabledNonUsers]  # type: ignore
    serializer_class = MetadataSerializer

    def _get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = set(_COMIC_VALUE_FIELD_NAMES)
        if (
            not (self._is_enabled_folder_view() and self.is_admin())
            or self.group not in _PATH_GROUPS
        ):
            fields -= _ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
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
            full_field = self.rel_prefix + field

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
            size_func = self.get_aggregate_func(self.model, "size")
            qs = qs.annotate(size=size_func)
        return self.annotate_common_aggregates(qs, self.model, {})

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
                _COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=_COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )
        elif self.is_admin() or self._is_enabled_folder_view():
            qs = qs.annotate(library_path=F("library__path"))
            querysets = (simple_qs, qs)

        # Foreign Keys with special count values
        _, qs = self._intersection_annotate(
            querysets,
            _COMIC_RELATED_VALUE_FIELDS,
        )
        return qs

    @staticmethod
    def _get_intersection_queryset(qs, count_rel, comic_pks):
        """Create an intersection queryset."""
        return (
            qs.annotate(count=Count(count_rel))
            .order_by()
            .filter(count=comic_pks.count())
        )

    def _query_m2m_intersections(self, simple_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}
        pk_field = self.rel_prefix + "pk"
        comic_pks = simple_qs.values_list(pk_field, flat=True)
        for field_name in COMIC_M2M_FIELD_NAMES:
            model = Comic._meta.get_field(field_name).related_model
            if not model:
                reason = f"No model found for comic field: {field_name}"
                raise ValueError(reason)

            intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
            # order_by() is very important for grouping
            intersection_qs = self._get_intersection_queryset(
                intersection_qs, "comic", comic_pks
            )
            m2m_intersections[field_name] = intersection_qs
        return m2m_intersections

    def _path_security(self, obj):
        """Secure filesystem information for acl situation."""
        is_path_group = self.group in _PATH_GROUPS
        if is_path_group:
            if self.is_admin():
                return
            if self._is_enabled_folder_view():
                library_path = obj.library_path
                obj.path = obj.path.removeprefix(library_path)
        else:
            obj.path = ""

    def _highlight_current_group(self, obj):
        """Values for highlighting the current group."""
        obj.group = self.group
        if self.model and not self.is_model_comic:
            # move the name of the group to the correct field
            group_field = self.model.__name__.lower()
            group_obj = {"pk": obj.pk, "name": obj.name}
            setattr(obj, group_field, group_obj)
            obj.name = None

    @staticmethod
    def _get_optimized_m2m_query(key, qs):
        # XXX The prefetch gets removed by field.set() :(
        if key == "contributors":
            optimized_qs = qs.prefetch_related(*_CONTRIBUTOR_RELATIONS).only(
                *_CONTRIBUTOR_RELATIONS
            )
        elif key == "story_arc_numbers":
            optimized_qs = qs.prefetch_related("story_arc").only("story_arc", "number")
        elif key == "identifiers":
            optimized_qs = qs.prefetch_related("identifier_type").only(
                "identifier_type", "nss", "url"
            )
        else:
            optimized_qs = qs.only("name")
        return optimized_qs

    @classmethod
    def _copy_m2m_intersections(cls, obj, m2m_intersections):
        """Copy the m2m intersections into the object."""
        for key, value in m2m_intersections.items():
            optimized_qs = cls._get_optimized_m2m_query(key, value)
            if hasattr(obj, key):
                # real db fields need to use their special set method.
                field = getattr(obj, key)
                field.set(optimized_qs)
            else:
                # fake db field is just a queryset attached.
                setattr(obj, key, optimized_qs)

    @staticmethod
    def _copy_conflicting_simple_fields(obj):
        for field in _COMIC_VALUE_FIELDS_CONFLICTING:
            """Copy conflicting fields over naturral fields."""
            conflict_field = _COMIC_VALUE_FIELDS_CONFLICTING_PREFIX + field
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
            obj.filename = obj.filename()

        return obj

    def get_object(self):
        """Create a comic-like object from the current browser group."""
        # Comic model goes through the same code path as groups because
        # values dicts don't copy relations to the serializer. The values
        # dict is necessary because of the folders view union in browser.py.

        if self.model is None:
            raise NotFound(detail=f"Cannot get metadata for {self.group=}")

        search_scores: dict = self.get_search_scores()
        object_filter = self.get_query_filters_without_group(self.model, search_scores)
        pk = self.kwargs["pk"]
        qs = self.model.objects.filter(object_filter, pk=pk)

        qs = self._annotate_aggregates(qs)
        simple_qs = qs

        qs = self._annotate_values_and_fks(qs, simple_qs)

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
        return self._copy_annotations_into_comic_fields(obj, m2m_intersections)

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
    def get(self, *_args, **_kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        try:
            self._efv_flag = None
            self.parse_params()
            self.group = self.kwargs["group"]
            self._validate()
            self.set_rel_prefix(self.model)
            self.set_order_key()

            obj = self.get_object()

            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Exception:
            LOG.exception(f"Getting metadata {self.kwargs}")
