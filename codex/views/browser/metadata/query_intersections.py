"""Metadata query fk & m2m intersections."""

from django.db.models import Count
from icecream import ic

from codex.librarian.importer.const import COMIC_FK_FIELDS, COMIC_M2M_FIELDS
from codex.models import Comic
from codex.models.functions import JsonGroupArray
from codex.views.browser.metadata.annotate import MetadataAnnotateView
from codex.views.browser.metadata.const import (
    COMIC_FK_MAIN_FIELDS,
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
            qs = qs.only("name").distinct()
            qs = qs.group_by("name")  # pyright:ignore[reportAttributeAccessIssue]
            qs = qs.annotate(ids=JsonGroupArray("id", distinct=True))
            qs = qs.values("ids", "name")
            groups[field_name] = qs
        return groups

    @staticmethod
    def _get_optimized_m2m_query(qs):
        optimizers = M2M_QUERY_OPTIMIZERS.get(qs.model, {})
        if prefetch := optimizers.get("prefetch"):
            qs = qs.prefetch_related(*prefetch)
        if select := optimizers.get("select"):
            qs = qs.select_related(*select)
        only = optimizers.get("only", ("name",))
        return qs.only(*only)

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
        return self._get_optimized_m2m_query(intersection_qs)

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

        for field in COMIC_M2M_FIELDS:
            m2m_intersections[field.name] = self._get_m2m_intersection_query(
                field.name, comic_pks, comic_pks_count
            )
            ic(field.name, m2m_intersections[field.name].values())
        return m2m_intersections

    def _get_fk_intersection_query(
        self, field_name, comic_pks, comic_pks_count, back_rel=None
    ):
        """Get intersection query for one field."""
        model = Comic._meta.get_field(field_name).related_model
        if not model:
            reason = f"No model found for comic field: {field_name}"
            raise ValueError(reason)

        rel = back_rel + "__in" if back_rel else "comic__pk__in"
        intersection_qs = model.objects.filter(**{rel: comic_pks})
        intersection_qs = intersection_qs.alias(count=Count("comic")).filter(
            count=comic_pks_count
        )
        return intersection_qs.only("name")

    def _query_fk_intersections(self, filtered_qs):
        fk_intersections = {}
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.distinct().values_list(pk_field, flat=True)
        # In fts mode the join doesn't work for the query.
        # Evaluating it now is probably faster than running the filter for every m2m anyway.
        comic_pks = set(comic_pks)
        comic_pks_count = len(comic_pks)

        for field in COMIC_FK_FIELDS:
            if field.name in ("main_character", "main_team"):
                continue
            fk_intersections[field.name] = self._get_fk_intersection_query(
                field.name, comic_pks, comic_pks_count
            )
        return fk_intersections

    def _query_fk_main_intersections(self, filtered_qs):
        fk_intersections = {}
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.distinct().values_list(pk_field, flat=True)
        # In fts mode the join doesn't work for the query.
        # Evaluating it now is probably faster than running the filter for every m2m anyway.
        comic_pks = set(comic_pks)
        comic_pks_count = len(comic_pks)

        for field, back_rel in COMIC_FK_MAIN_FIELDS.items():
            fk_intersections[field.name] = self._get_fk_intersection_query(
                field.name, comic_pks, comic_pks_count, back_rel
            )
        return fk_intersections

    def query_intersections(self, filtered_qs):
        """Query complex intersections."""
        groups = self._query_groups()
        fk_intersections = self._query_fk_intersections(filtered_qs)
        fk_main_intersections = self._query_fk_main_intersections(filtered_qs)
        fk_intersections.update(fk_main_intersections)
        m2m_intersections = self._query_m2m_intersections(filtered_qs)
        return groups, fk_intersections, m2m_intersections
