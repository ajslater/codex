"""View for marking comics read and unread."""

from types import MappingProxyType
from typing import ClassVar

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Count, IntegerField, Sum, Value
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.librarian.importer.const import COMIC_M2M_FIELD_NAMES
from codex.logger.logging import get_logger
from codex.models import AdminFlag, Comic
from codex.serializers.browser.metadata import MetadataSerializer
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
    {"id", "pk", "sort_name", "stat"} | _COMIC_VALUE_FIELDS_CONFLICTING
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
_SUM_FIELDS = frozenset({"page_count", "size"})
_GROUP_RELS = frozenset({"publisher", "imprint", "series", "volume"})


class MetadataView(BrowserAnnotationsView):
    """Comic metadata."""

    permission_classes: ClassVar[list] = [IsAuthenticatedOrEnabledNonUsers]  # type: ignore
    serializer_class = MetadataSerializer
    TARGET = "metadata"
    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType(
        {
            AdminFlag.FlagChoices.FOLDER_VIEW.value: "folder_view",
            AdminFlag.FlagChoices.DYNAMIC_GROUP_COVERS.value: "dynamic_group_covers",
        }
    )

    def _get_comic_value_fields(self):
        """Include the path field for staff."""
        fields = set(_COMIC_VALUE_FIELD_NAMES)
        group = self.kwargs["group"]
        if (
            not (self.admin_flags["folder_view"] and self.is_admin())
            or group not in _PATH_GROUPS
        ):
            fields -= _ADMIN_OR_FILE_VIEW_ENABLED_COMIC_VALUE_FIELDS
        return tuple(fields)

    def _intersection_annotate(
        self,
        querysets,
        fields,
        related_suffix="",
        annotation_prefix="",
    ):
        """Annotate the intersection of value and fk fields."""
        (filtered_qs, qs) = querysets
        for field in fields:
            # Annotate variant counts
            # If 1 variant, annotate value, otherwise None
            ann_field = annotation_prefix + field.replace("__", "_")

            full_field = self.rel_prefix + field

            if field in _SUM_FIELDS:
                val = Sum(full_field)
            else:
                # group_by makes the filter work, but prevents its
                # use as a subquery in the big query.
                group_by = self.get_group_by()
                sq = (
                    filtered_qs.alias(filter_count=Count(full_field, distinct=True))
                    .filter(filter_count=1)
                    .group_by(group_by)
                    .values_list(full_field + related_suffix, flat=True)
                )
                try:
                    val = sq[0]
                except IndexError:
                    val = None
                if field.endswith("count"):
                    output_field = IntegerField()
                else:
                    output_field = Comic._meta.get_field(field).__class__()
                val = Value(val, output_field)
            qs = qs.annotate(**{ann_field: val})

        return filtered_qs, qs

    def _annotate_values_and_fks(self, qs, filtered_qs):
        """Annotate comic values and comic foreign key values."""
        # Simple Values
        querysets = (filtered_qs, qs)
        if not self.is_model_comic:
            comic_value_fields = self._get_comic_value_fields()
            querysets = self._intersection_annotate(querysets, comic_value_fields)

            # Conflicting Simple Values
            querysets = self._intersection_annotate(
                querysets,
                _COMIC_VALUE_FIELDS_CONFLICTING,
                annotation_prefix=_COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
            )

        # Foreign Keys with special count values
        _, qs = self._intersection_annotate(
            querysets,
            _COMIC_RELATED_VALUE_FIELDS,
        )
        return qs

    def _query_m2m_intersections(self, filtered_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.values_list(pk_field, flat=True)
        comic_pks_count = comic_pks.count()
        for field_name in COMIC_M2M_FIELD_NAMES | _GROUP_RELS:
            try:
                if (
                    field_name in _GROUP_RELS
                    and self.model
                    and not self.model._meta.get_field(field_name)
                ):
                    continue
            except FieldDoesNotExist:
                continue

            model = Comic._meta.get_field(field_name).related_model
            if not model:
                reason = f"No model found for comic field: {field_name}"
                raise ValueError(reason)

            intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
            if field_name in _GROUP_RELS:
                group_by = "name" if field_name == "volume" else "sort_name"
                intersection_qs = intersection_qs.group_by(group_by)
            intersection_qs = intersection_qs.alias(count=Count("comic")).filter(
                count=comic_pks_count
            )

            m2m_intersections[field_name] = intersection_qs
        return m2m_intersections

    def _path_security(self, obj):
        """Secure filesystem information for acl situation."""
        group = self.kwargs["group"]
        is_path_group = group in _PATH_GROUPS
        if is_path_group:
            if self.is_admin():
                return
            if self.admin_flags["folder_view"]:
                obj.path = obj.search_path()
        else:
            obj.path = ""

    def _highlight_current_group(self, obj):
        """Values for highlighting the current group."""
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
            if hasattr(obj, key) and key not in _GROUP_RELS:
                # real db fields need to use their special set method.
                field = getattr(obj, key)
                field.set(optimized_qs)
            else:
                # fake db field is just a queryset attached.
                if key in _GROUP_RELS:
                    optimized_qs = optimized_qs[0] if len(optimized_qs) else None
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

        return obj

    def _raise_not_found(self, exc=None):
        """Raise an exception if the object is not found."""
        pks = self.kwargs["pks"]
        group = self.kwargs["group"]
        detail = f"Filtered metadata for {group}/{pks} not found"
        raise NotFound(detail=detail) from exc

    def get_object(self):
        """Create a comic-like object from the current browser group."""
        # Comic model goes through the same code path as groups because
        # values dicts don't copy relations to the serializer. The values
        # dict is necessary because of the folders view union in browser.py.

        if self.model is None:
            # TODO this looks redundant after set_browse_model
            group = self.kwargs["group"]
            raise NotFound(detail=f"Cannot get metadata for {group=}")

        object_filter = self.get_query_filters_without_group(self.model)  # type: ignore
        pks = self.kwargs["pks"]
        qs = self.model.objects.filter(object_filter, pk__in=pks)
        qs = self.filter_by_annotations(qs, self.model, binary=True)
        filtered_qs = qs
        qs = self.annotate_order_aggregates(qs, self.model)
        qs = self.annotate_card_aggregates(qs, self.model)
        qs = self.annotate_for_metadata(qs, self.model)
        group_by = self.get_group_by()
        qs = qs.group_by(group_by)
        qs = self._annotate_values_and_fks(qs, filtered_qs)

        qs_list = self.re_cover_multi_groups(qs)

        try:
            obj = qs_list[0]
            if not obj:
                reason = "Empty obj"
                raise ValueError(reason)  # noqa TRY301
        except (IndexError, ValueError) as exc:
            self._raise_not_found(exc)

        m2m_intersections = self._query_m2m_intersections(filtered_qs)
        return self._copy_annotations_into_comic_fields(obj, m2m_intersections)  # type: ignore

    def set_valid_browse_nav_groups(self, _valid_top_groups):
        """Limited allowed nav groups for metadata."""
        group = self.kwargs["group"]
        self.valid_nav_groups = (group,)

    @extend_schema(request=BrowserAnnotationsView.input_serializer_class)
    def get(self, *_args, **_kwargs):
        """Get metadata for a filtered browse group."""
        # Init
        try:
            self.init_request()
            obj = self.get_object()
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        except Exception:
            LOG.exception(f"Getting metadata {self.kwargs}")
