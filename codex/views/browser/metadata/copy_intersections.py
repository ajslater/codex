"""Copy Intersections Into Comic Fields."""

from codex.models.comic import Comic
from codex.serializers.browser.metadata import PREFETCH_PREFIX
from codex.views.browser.metadata.collection_list import (
    annotate_collection_list,
    collection_list_field_name,
)
from codex.views.browser.metadata.const import (
    COMIC_VALUE_FIELDS_CONFLICTING,
    COMIC_VALUE_FIELDS_CONFLICTING_PREFIX,
    PATH_COLLECTIONS,
)
from codex.views.browser.metadata.query_intersections import (
    MetadataQueryIntersectionsView,
)

_PREFETCH_DICT_FIELDS = frozenset({"identifiers", "credits", "story_arc_numbers"})


class MetadataCopyIntersectionsView(MetadataQueryIntersectionsView):
    """Copy Intersections Into Comic Fields."""

    def _path_security(self, obj) -> None:
        """Secure filesystem information for acl situation."""
        collection = self.kwargs["collection"]
        is_path_collection = collection in PATH_COLLECTIONS
        if is_path_collection:
            if self.is_admin:
                return
            if self.admin_flags["folder_view"]:
                # Non-staff folder viewers see the library-relative path only;
                # the absolute server layout stays hidden. obj.path may be None
                # for a conflicting/absent intersection (this runs after
                # _copy_conflicting_simple_fields), so guard search_path.
                obj.path = obj.search_path() if obj.path else ""
            else:
                obj.path = ""
        else:
            obj.path = ""

    def _highlight_current_collection(self, obj) -> None:
        """Values for highlighting the current collection."""
        if self.model and self.model is not Comic:
            field = collection_list_field_name(self.model)
            qs = self.model.objects.filter(pk__in=obj.ids)
            setattr(obj, field, annotate_collection_list(qs))
            obj.name = None

    @classmethod
    def _copy_m2m_intersections(cls, obj, m2m_intersections) -> None:
        """Copy the m2m intersections into the object."""
        # It might even be faster to copy everything to a dict and not use the obj.
        for key, qs in m2m_intersections.items():
            serializer_key = (
                f"{PREFETCH_PREFIX}{key}" if key in _PREFETCH_DICT_FIELDS else key
            )
            if hasattr(obj, serializer_key):
                # Real m2m field — the Comic path: ``obj`` is a live saved
                # instance, so serve the intersection through the prefetch
                # cache (RelatedManager.get_queryset consults it, keyed by
                # field name). NEVER ManyRelatedManager.set() here: this is
                # a GET, and set(clear=True) DELETE+INSERTs the through
                # tables — on a multi-comic selection it permanently
                # rewrote the first comic's tags to the intersection.
                cache = getattr(obj, "_prefetched_objects_cache", None)
                if cache is None:
                    cache = {}
                    obj._prefetched_objects_cache = cache  # noqa: SLF001
                cache[serializer_key] = qs
            else:
                # fake db field is just a queryset attached.
                setattr(obj, serializer_key, qs)

    @staticmethod
    def _copy_collection_lists(obj, collection_lists) -> None:
        for field, collection_qs in collection_lists.items():
            setattr(obj, field + "_list", collection_qs)

    @staticmethod
    def _copy_fks(obj, fks) -> None:
        for field, fk_qs in fks.items():
            setattr(obj, field, fk_qs.first())

    @staticmethod
    def _copy_conflicting_simple_fields(obj) -> None:
        for field in COMIC_VALUE_FIELDS_CONFLICTING:
            """Copy conflicting fields over naturral fields."""
            conflict_field = COMIC_VALUE_FIELDS_CONFLICTING_PREFIX + field
            val = getattr(obj, conflict_field, None)
            setattr(obj, field, val)

    def copy_intersections_into_comic_fields(
        self, obj, collection_lists, fk_intersections, m2m_intersections
    ):
        """Copy a bunch of values that i couldn't fit cleanly in the main queryset."""
        self._highlight_current_collection(obj)
        self._copy_collection_lists(obj, collection_lists)
        self._copy_fks(obj, fk_intersections)
        self._copy_m2m_intersections(obj, m2m_intersections)
        if self.model is not Comic:
            self._copy_conflicting_simple_fields(obj)
        # Run last so per-tier path scrubbing is the final word for every
        # collection: _copy_conflicting_simple_fields overwrites obj.path for
        # non-comic collections, which would otherwise undo securing it first.
        self._path_security(obj)

        return obj
