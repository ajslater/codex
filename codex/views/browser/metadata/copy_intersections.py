"""Copy Intersections Into Comic Fields."""

from codex.models.comic import Comic
from codex.serializers.browser.metadata import PREFETCH_PREFIX
from codex.views.browser.metadata.const import (
    COMIC_VALUE_FIELDS_CONFLICTING,
    COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
    PATH_GROUPS,
)
from codex.views.browser.metadata.query_intersections import (
    MetadataQueryIntersectionsView,
)

_PREFETCH_DICT_FIELDS = frozenset({"identifiers", "credits", "story_arc_numbers"})


class MetadataCopyIntersectionsView(MetadataQueryIntersectionsView):
    """Copy Intersections Into Comic Fields."""

    def _path_security(self, obj):
        """Secure filesystem information for acl situation."""
        group = self.kwargs["group"]
        is_path_group = group in PATH_GROUPS
        if is_path_group:
            if self.is_admin:
                return
            if self.admin_flags["folder_view"]:
                obj.path = obj.search_path()
        else:
            obj.path = ""

    def _highlight_current_group(self, obj):
        """Values for highlighting the current group."""
        if self.model and self.model is not Comic:
            # move the name of the group to the correct field
            field = self.model.__name__.lower() + "_list"
            group_list = self.model.objects.filter(pk__in=obj.ids).values("name")
            setattr(obj, field, group_list)
            obj.name = None

    @classmethod
    def _copy_m2m_intersections(cls, obj, m2m_intersections):
        """Copy the m2m intersections into the object."""
        # It might even be faster to copy everything to a dict and not use the obj.
        for key, qs in m2m_intersections.items():
            serializer_key = (
                f"{PREFETCH_PREFIX}{key}" if key in _PREFETCH_DICT_FIELDS else key
            )
            if hasattr(obj, serializer_key):
                # real db fields need to use their special set method.
                field = getattr(obj, serializer_key)
                field.set(qs, clear=True)
            else:
                # fake db field is just a queryset attached.
                setattr(obj, serializer_key, qs)

    @staticmethod
    def _copy_groups(obj, groups):
        for field, group_qs in groups.items():
            setattr(obj, field + "_list", group_qs)

    @staticmethod
    def _copy_fks(obj, fks):
        for field, fk_qs in fks.items():
            setattr(obj, field, fk_qs.first())

    @staticmethod
    def _copy_conflicting_simple_fields(obj):
        for field in COMIC_VALUE_FIELDS_CONFLICTING:
            """Copy conflicting fields over naturral fields."""
            conflict_field = COMIC_VALUE_FIELDS_CONFLICTING_PREFIX + field
            val = getattr(obj, conflict_field, None)
            setattr(obj, field, val)

    def copy_intersections_into_comic_fields(
        self, obj, groups, fk_intersections, m2m_intersections
    ):
        """Copy a bunch of values that i couldn't fit cleanly in the main queryset."""
        self._path_security(obj)
        self._highlight_current_group(obj)
        self._copy_groups(obj, groups)
        self._copy_fks(obj, fk_intersections)
        self._copy_m2m_intersections(obj, m2m_intersections)
        if self.model is not Comic:
            self._copy_conflicting_simple_fields(obj)

        return obj
