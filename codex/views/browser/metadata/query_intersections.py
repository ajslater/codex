"""Metadata query fk & m2m intersections."""

from django.db.models import Count
from django.db.models.query import QuerySet

from codex.librarian.scribe.importer.const import COMIC_FK_FIELDS, COMIC_M2M_FIELDS
from codex.models import Comic
from codex.models.functions import JsonGroupArray
from codex.models.groups import Volume
from codex.views.browser.metadata.annotate import MetadataAnnotateView
from codex.views.browser.metadata.const import (
    COMIC_MAIN_FIELD_NAME_BACK_REL_MAP,
    GROUP_MODELS,
    M2M_QUERY_OPTIMIZERS,
)
from codex.views.const import METADATA_GROUP_RELATION, MODEL_REL_MAP


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

        for model in GROUP_MODELS.get(group, ()):
            field_name = MODEL_REL_MAP[model]
            qs = model.objects.filter(**group_filter)
            only = ["name"]
            if model is Volume:
                only.append("number_to")
            qs = qs.only(*only).distinct()
            qs = qs.group_by(*only)
            qs = qs.annotate(ids=JsonGroupArray("id", distinct=True))
            qs = qs.values("ids", *only)
            groups[field_name] = qs
        return groups

    @staticmethod
    def _get_optimized_m2m_query(qs):
        optimizers = M2M_QUERY_OPTIMIZERS.get(qs.model, {})
        if prefetch := optimizers.get("prefetch"):
            qs = qs.prefetch_related(*prefetch)
        if select := optimizers.get("select", ("identifier",)):
            qs = qs.select_related(*select)
        only = optimizers.get("only", ("name", "identifier"))
        return qs.only(*only)

    def _get_m2m_intersection_query(self, field_name: str, comic_pks: frozenset[int]):
        """Get intersection query for one field."""
        model = Comic._meta.get_field(field_name).related_model
        if not model:
            reason = f"No model found for comic field: {field_name}"
            raise ValueError(reason)

        intersection_qs = model.objects.filter(comic__pk__in=comic_pks)
        intersection_qs = intersection_qs.alias(count=Count("comic")).filter(
            count=len(comic_pks)
        )
        return self._get_optimized_m2m_query(intersection_qs)

    def _get_comic_pks(self, filtered_qs: QuerySet) -> frozenset[int]:
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.distinct().values_list(pk_field, flat=True)
        # In fts mode the join doesn't work for the query.
        # Evaluating it now is probably faster than running the filter for every m2m anyway.
        return frozenset(comic_pks)

    def _query_m2m_intersections(self, comic_pks: frozenset[int]):
        """Query the through models to figure out m2m intersections."""
        # Speed ok, but still does a query per m2m model
        m2m_intersections = {}

        for field in COMIC_M2M_FIELDS:
            m2m_intersections[field.name] = self._get_m2m_intersection_query(
                field.name, comic_pks
            )
        return m2m_intersections

    def _get_fk_intersection_query(
        self, field_name: str, comic_pks: frozenset[int], rel: str
    ):
        """Get intersection query for one field."""
        model = Comic._meta.get_field(field_name).related_model
        if not model:
            reason = f"No model found for comic field: {field_name}"
            raise ValueError(reason)

        rel += "__in"
        intersection_qs = model.objects.filter(**{rel: comic_pks})
        intersection_qs = intersection_qs.alias(count=Count("comic")).filter(
            count=len(comic_pks)
        )
        return intersection_qs.only("name")

    def _query_fk_intersections(self, comic_pks: frozenset[int]):
        fk_intersections = {}

        for field in COMIC_FK_FIELDS:
            rel = COMIC_MAIN_FIELD_NAME_BACK_REL_MAP.get(field.name, "comic__pk")
            fk_intersections[field.name] = self._get_fk_intersection_query(
                field.name, comic_pks, rel
            )
        return fk_intersections

    def query_intersections(self, filtered_qs):
        """Query complex intersections."""
        groups = self._query_groups()
        comic_pks = self._get_comic_pks(filtered_qs)
        fk_intersections = self._query_fk_intersections(comic_pks)
        m2m_intersections = self._query_m2m_intersections(comic_pks)
        return groups, fk_intersections, m2m_intersections
