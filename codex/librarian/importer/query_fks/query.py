"""Query the missing foreign keys methods."""

from types import MappingProxyType

from django.db.models import Q

from codex.librarian.importer.query_fks.covers import QueryCustomCoversImporter
from codex.models import (
    Credit,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArcNumber,
    Volume,
)
from codex.models.named import Identifier
from codex.settings.settings import FILTER_BATCH_SIZE

_CLASS_QUERY_FIELDS_MAP = MappingProxyType(
    {
        Credit: ("role__name", "person__name"),
        StoryArcNumber: ("story_arc__name", "number"),
        Folder: ("path",),
        Imprint: ("publisher__name", "name"),
        Series: ("publisher__name", "imprint__name", "name"),
        Volume: ("publisher__name", "imprint__name", "series__name", "name"),
        Identifier: ("identifier_type__name", "nss"),
    }
)
_DEFAULT_QUERY_FIELDS = ("name",)
_EXTRA_UPDATE_FIELDS_MAP = MappingProxyType(
    {Series: ("volume_count",), Volume: ("issue_count",)}
)


class QueryForeignKeysQueryImporter(QueryCustomCoversImporter):
    """Query the missing foreign keys methods."""

    @staticmethod
    def query_existing_mds(fk_model, fk_filter, extra_fields=None):
        """Query existing metatata tables."""
        fields = _CLASS_QUERY_FIELDS_MAP.get(fk_model, _DEFAULT_QUERY_FIELDS)
        if extra_fields:
            fields += extra_fields
        flat = len(fields) == 1 and fk_model != Publisher
        qs = (
            fk_model.objects.filter(fk_filter)
            .distinct()
            .values_list(*fields, flat=flat)
        )
        return frozenset(qs)

    def query_create_metadata(  # noqa: PLR0913
        self,
        fk_model,
        create_mds,
        update_mds,
        q_obj: Q,
        status,
        and_q_obj: Q | None = None,
    ):
        """Get create metadata by comparing proposed meatada to existing rows."""
        vnp = fk_model._meta.verbose_name_plural.title()
        status.subtitle = vnp
        offset = 0
        num_qs = len(q_obj.children)
        while offset < num_qs:
            # Do this in batches so as not to exceed the sqlite 1k expression tree depth limit
            # django.db.utils.OperationalError: Expression tree is too large (maximum depth 1000)
            children_chunk = q_obj.children[offset : offset + FILTER_BATCH_SIZE]
            filter_chunk = Q(*children_chunk, _connector=Q.OR)
            if and_q_obj:
                filter_chunk = and_q_obj & filter_chunk

            existing_mds = self.query_existing_mds(fk_model, filter_chunk)
            create_mds.difference_update(existing_mds)
            if extra_update_fields := _EXTRA_UPDATE_FIELDS_MAP.get(fk_model):
                # The mds that are in the existing_mds, but don't match the proposed mds with the extra update fields
                update_mds.update(existing_mds)
                match_with_extra_fields_mds = self.query_existing_mds(
                    fk_model, filter_chunk, extra_update_fields
                )
                update_mds.difference_update(match_with_extra_fields_mds)

            status.add_complete(len(filter_chunk))
            self.status_controller.update(status)

            offset += FILTER_BATCH_SIZE

        status.subtitle = ""

        return num_qs
