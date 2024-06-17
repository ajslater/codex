"""View for marking comics read and unread."""

from types import MappingProxyType

from django.db.models import Count, IntegerField, Sum, Value
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from codex.librarian.importer.const import (
    COMIC_M2M_FIELD_NAMES,
)
from codex.logger.logging import get_logger
from codex.models import AdminFlag, Comic
from codex.models.functions import JsonGroupArray
from codex.serializers.browser.metadata import PREFETCH_PREFIX, MetadataSerializer
from codex.serializers.browser.settings import BrowserFilterChoicesInputSerilalizer
from codex.views.browser.annotations import BrowserAnnotationsView
from codex.views.const import METADATA_GROUP_RELATION

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
_PATH_GROUPS = frozenset({"c", "f"})
_CONTRIBUTOR_RELATIONS = ("role", "person")
_SUM_FIELDS = frozenset({"page_count", "size"})
_GROUP_RELS = MappingProxyType(
    {
        "i": ("publisher",),
        "s": (
            "publisher",
            "imprint",
        ),
        "v": (
            "publisher",
            "imprint",
            "series",
        ),
        "c": ("publisher", "imprint", "series", "volume"),
    }
)


class MetadataView(BrowserAnnotationsView):
    """Comic metadata."""

    serializer_class = MetadataSerializer
    input_serializer_class = BrowserFilterChoicesInputSerilalizer
    TARGET = "metadata"
    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType(
        {
            AdminFlag.FlagChoices.FOLDER_VIEW.value: "folder_view",
        }
    )

    def init_request(self):
        """Initialize request."""
        self.set_admin_flags()
        self.parse_params()
        self.set_model()
        self.set_rel_prefix()

    def set_valid_browse_nav_groups(self, valid_top_groups):  # noqa: ARG002
        """Limited allowed nav groups for metadata."""
        group = self.kwargs["group"]
        self.valid_nav_groups = (group,)

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
                sq = filtered_qs.alias(
                    filter_count=Count(full_field, distinct=True)
                ).filter(filter_count=1)
                sq = self.add_group_by(sq)
                sq = sq.values_list(full_field + related_suffix, flat=True)
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

    def _query_groups(self):
        """Query the through models to show group lists."""
        groups = {}
        if not self.model:
            return groups
        group = self.kwargs["group"]
        rel = METADATA_GROUP_RELATION.get(group)
        if not rel:
            return groups
        rel = rel + "__in"
        pks = self.kwargs["pks"]
        group_filter = {rel: pks}

        for field_name in _GROUP_RELS.get(group, ()):
            field = self.model._meta.get_field(field_name)
            model = field.related_model
            if not model:
                continue

            qs = model.objects.filter(**group_filter)
            qs = qs.only("name").distinct()
            qs = qs.group_by("name")
            qs = qs.annotate(ids=JsonGroupArray("id", distinct=True))
            qs = qs.values("ids", "name")
            groups[field_name] = qs
        return groups

    @staticmethod
    def _get_optimized_m2m_query(key, qs):
        if key == "contributors":
            qs = qs.prefetch_related(*_CONTRIBUTOR_RELATIONS)
            qs = qs.only(*_CONTRIBUTOR_RELATIONS)
        elif key == "story_arc_numbers":
            qs = qs.select_related("story_arc")
            qs = qs.only("story_arc", "number")
        elif key == "identifiers":
            qs = qs.select_related("identifier_type")
            qs = qs.only("identifier_type", "nss", "url")
        else:
            qs = qs.only("name")
        return qs

    def _query_m2m_intersections(self, filtered_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.values_list(pk_field, flat=True)
        comic_pks_count = comic_pks.count()
        for field_name in COMIC_M2M_FIELD_NAMES:
            model = Comic._meta.get_field(field_name).related_model
            if not model:
                reason = f"No model found for comic field: {field_name}"
                raise ValueError(reason)

            intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
            intersection_qs = intersection_qs.alias(count=Count("comic")).filter(
                count=comic_pks_count
            )
            intersection_qs = self._get_optimized_m2m_query(field_name, intersection_qs)

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
            field = self.model.__name__.lower() + "_list"
            group_list = self.model.objects.filter(pk__in=obj.ids).values("name")
            setattr(obj, field, group_list)
            obj.name = None

    @classmethod
    def _copy_m2m_intersections(cls, obj, m2m_intersections):
        """Copy the m2m intersections into the object."""
        # XXX It might even be faster to copy everything to a dict and not use the obj.
        for key, qs in m2m_intersections.items():
            serializer_key = (
                f"{PREFETCH_PREFIX}{key}"
                if key in ("identifiers", "contributors", "story_arc_numbers")
                else key
            )
            if hasattr(obj, serializer_key):
                # real db fields need to use their special set method.
                field = getattr(obj, serializer_key)
                field.set(
                    qs,
                    clear=True,
                )
            else:
                # fake db field is just a queryset attached.
                setattr(obj, serializer_key, qs)

    @staticmethod
    def _copy_groups(obj, groups):
        for field, group_qs in groups.items():
            setattr(obj, field + "_list", group_qs)

    @staticmethod
    def _copy_conflicting_simple_fields(obj):
        for field in _COMIC_VALUE_FIELDS_CONFLICTING:
            """Copy conflicting fields over naturral fields."""
            conflict_field = _COMIC_VALUE_FIELDS_CONFLICTING_PREFIX + field
            val = getattr(obj, conflict_field)
            setattr(obj, field, val)

    def _copy_annotations_into_comic_fields(self, obj, groups, m2m_intersections):
        """Copy a bunch of values that i couldn't fit cleanly in the main queryset."""
        self._path_security(obj)
        self._highlight_current_group(obj)
        self._copy_groups(obj, groups)
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

        qs = self.get_filtered_queryset(self.model)

        filtered_qs = qs
        qs = self.annotate_order_aggregates(qs, self.model)
        qs = self.annotate_card_aggregates(qs, self.model)
        qs = self._annotate_values_and_fks(qs, filtered_qs)
        qs = self.add_group_by(qs)

        try:
            obj = qs[0]
            if not obj:
                reason = "Empty obj"
                raise ValueError(reason)  # noqa TRY301
        except (IndexError, ValueError) as exc:
            self._raise_not_found(exc)

        groups = self._query_groups()
        m2m_intersections = self._query_m2m_intersections(filtered_qs)
        return self._copy_annotations_into_comic_fields(obj, groups, m2m_intersections)  # type: ignore

    @extend_schema(parameters=[input_serializer_class])
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
