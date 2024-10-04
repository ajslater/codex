"""Metadata query fk & m2m intersections."""

from types import MappingProxyType

from django.db.models import Count

from codex.librarian.importer.const import COMIC_M2M_FIELD_NAMES
from codex.logger.logging import get_logger
from codex.models import Comic
from codex.models.functions import JsonGroupArray
from codex.views.browser.metadata.annotate import MetadataAnnotateView
from codex.views.const import METADATA_GROUP_RELATION

LOG = get_logger(__name__)
_CONTRIBUTOR_RELATIONS = ("role", "person")
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


class MetadataQueryIntersectionsView(MetadataAnnotateView):
    """Metadata query fk & m2m intersections."""

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

    def _get_m2m_intersection_query(self, field_name, comic_pks, comic_pks_count):
        """Get intersection query for one field."""
        model = Comic._meta.get_field(field_name).related_model
        if not model:
            reason = f"No model found for comic field: {field_name}"
            raise ValueError(reason)

        intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
        intersection_qs = intersection_qs.alias(count=Count("comic")).filter(
            count=comic_pks_count
        )
        return self._get_optimized_m2m_query(field_name, intersection_qs)

    def _query_m2m_intersections(self, filtered_qs):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.distinct().values_list(pk_field, flat=True)
        # In fts mode the join doesn't work for the query.
        # Evaluating it now is probably faster than running the filter for every m2m anyway.
        comic_pks = set(comic_pks)
        comic_pks_count = len(comic_pks)

        for field_name in COMIC_M2M_FIELD_NAMES:
            m2m_intersections[field_name] = self._get_m2m_intersection_query(
                field_name, comic_pks, comic_pks_count
            )
        return m2m_intersections

    def query_intersections(self, filtered_qs):
        """Query complex intersections."""
        groups = self._query_groups()
        m2m_intersections = self._query_m2m_intersections(filtered_qs)
        return groups, m2m_intersections
