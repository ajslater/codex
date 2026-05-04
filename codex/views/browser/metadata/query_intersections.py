"""Metadata query fk & m2m intersections."""

from django.db.models import CharField, Count, F, ManyToManyField, Value
from django.db.models.query import QuerySet

from codex.librarian.scribe.importer.const import COMIC_FK_FIELDS, COMIC_M2M_FIELDS
from codex.models import Comic
from codex.models.functions import JsonGroupArray
from codex.models.groups import Volume
from codex.views.browser.metadata.annotate import MetadataAnnotateView
from codex.views.browser.metadata.const import (
    COMIC_MAIN_FIELD_NAME_BACK_REL_MAP,
    FK_QUERY_OPTIMIZERS,
    GROUP_MODELS,
    M2M_QUERY_OPTIMIZERS,
)
from codex.views.const import METADATA_GROUP_RELATION, MODEL_REL_MAP


class MetadataQueryIntersectionsView(MetadataAnnotateView):
    """Metadata query fk & m2m intersections."""

    def _query_groups(self) -> dict:
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
            qs = qs.group_by(*only)  # pyright: ignore[reportAttributeAccessIssue]
            qs = qs.annotate(ids=JsonGroupArray("id", distinct=True, order_by="id"))
            qs = qs.values("ids", *only)
            groups[field_name] = qs
        return groups

    def _get_comic_pks(self, filtered_qs: QuerySet) -> frozenset[int]:
        pk_field = self.rel_prefix + "pk"
        comic_pks = filtered_qs.distinct().values_list(pk_field, flat=True)
        # In fts mode the join doesn't work for the query.
        # Evaluating it now is probably faster than running the filter for every m2m anyway.
        return frozenset(comic_pks)

    @staticmethod
    def _get_optimized_fk_query(qs):
        """
        Apply select_related + only() hints keyed on the FK model.

        Serializers read a couple of nested FKs (e.g. ``AgeRating.metron``,
        ``Character.identifier.url``). Without select_related, accessing
        those during serialization fires a second query per instance.
        """
        optimizers = FK_QUERY_OPTIMIZERS.get(qs.model, {})
        if select := optimizers.get("select"):
            qs = qs.select_related(*select)
        only = optimizers.get("only", ("name",))
        return qs.only(*only)

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
        return self._get_optimized_fk_query(intersection_qs)

    def _query_fk_intersections(self, comic_pks: frozenset[int]) -> dict:
        fk_intersections = {}

        for field in COMIC_FK_FIELDS:
            rel = COMIC_MAIN_FIELD_NAME_BACK_REL_MAP.get(field.name, "comic__pk")
            fk_intersections[field.name] = self._get_fk_intersection_query(
                field.name, comic_pks, rel
            )
        return fk_intersections

    @staticmethod
    def _get_m2m_intersection_query(
        field: ManyToManyField, comic_pks: frozenset[int], num_comics: int
    ) -> QuerySet:
        """Build a through table queryst for a ManyToManyField."""
        through = field.remote_field.through  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        rel_field_name = field.m2m_reverse_field_name()
        qs = through.objects.filter(comic_id__in=comic_pks)
        qs = qs.values(related_id=F(rel_field_name + "_id"))
        qs = qs.annotate(cnt=Count("comic_id"))
        qs = qs.filter(cnt=num_comics)
        qs = qs.annotate(field_name=Value(field.name, output_field=CharField()))
        return qs.values_list("field_name", "related_id")

    @staticmethod
    def _get_optimized_m2m_query(qs):
        optimizers = M2M_QUERY_OPTIMIZERS.get(qs.model, {})
        if prefetch := optimizers.get("prefetch"):
            qs = qs.prefetch_related(*prefetch)
        if select := optimizers.get("select", ("identifier",)):
            qs = qs.select_related(*select)
        only = optimizers.get("only", ("name", "identifier"))
        return qs.only(*only)

    def _query_m2m_intersections(self, comic_pks: frozenset[int]) -> dict:
        """Query m2m intersections with a single query."""
        num_comics = len(comic_pks)

        # Build one union query across all through tables
        queries = []
        for field in COMIC_M2M_FIELDS:
            qs = self._get_m2m_intersection_query(field, comic_pks, num_comics)
            queries.append(qs)

        combined = queries[0].union(*queries[1:], all=True)

        # Partition results by field name
        pk_map: dict[str, list[int]] = {}
        for field_name, related_id in combined:
            pk_map.setdefault(field_name, []).append(related_id)

        # Hydrate with ORM querysets (preserves select/prefetch optimizers).
        # Fields with no intersection get ``.none()`` rather than a filter
        # on an empty pk list — avoids the per-field optimizer setup cost
        # and, for the ``self.model is Comic`` path in ``_copy_m2m_intersections``,
        # skips pointless prefetch dispatches on an already-empty result.
        m2m_intersections = {}
        for field in COMIC_M2M_FIELDS:
            pks = pk_map.get(field.name, [])
            if not pks:
                m2m_intersections[field.name] = field.related_model.objects.none()
                continue
            qs = field.related_model.objects.filter(pk__in=pks)
            m2m_intersections[field.name] = self._get_optimized_m2m_query(qs)

        return m2m_intersections

    def query_intersections(self, filtered_qs) -> tuple[dict, dict, dict]:
        """Query complex intersections."""
        groups = self._query_groups()
        comic_pks = self._get_comic_pks(filtered_qs)
        fk_intersections = self._query_fk_intersections(comic_pks)
        m2m_intersections = self._query_m2m_intersections(comic_pks)
        return groups, fk_intersections, m2m_intersections
